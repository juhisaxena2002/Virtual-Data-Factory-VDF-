"""api.py — FastAPI wrapper around the synthgen SDK.

Single file. Zero changes to the SDK. Drop this at the repo root and run:

    uvicorn api:app --reload --port 8000

Endpoints
---------
POST   /api/generate                      — batch generation
WS     /api/ws/stream                     — live streaming over WebSocket
POST   /api/connectors/test               — test any connector config
GET    /api/sessions                      — list chat sessions
POST   /api/sessions                      — create session
GET    /api/sessions/{id}                 — get session + messages
DELETE /api/sessions/{id}                 — delete session
POST   /api/sessions/{id}/messages        — append message to session
GET    /api/health                        — health check

WebSocket protocol
------------------
Client → Server (JSON):
    { "prompt": "...", "backend": "gemini", "api_key": "...",
      "interval_sec": 1, "duration_sec": 60,
      "connector": { "type": "public-api", "url": "...", ... } }

    At any time during stream:
    { "action": "stop" }

Server → Client (JSON, one message per event):
    { "type": "status",  "message": "..." }
    { "type": "record",  "data": {...}, "index": N }
    { "type": "error",   "message": "..." }
    { "type": "done",    "total": N }
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid
from datetime import datetime
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger("vdf.api")

app = FastAPI(title="VDF API", version="1.0.0", description="Virtual Data Factory — synthgen SDK over HTTP + WebSocket")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory session store (swap for SQLite/Redis in production)
# ---------------------------------------------------------------------------

_sessions: dict[str, dict] = {}   # { session_id: { id, name, created_at, messages: [] } }


def _new_session(name: str = "New session") -> dict:
    sid = str(uuid.uuid4())
    session = {"id": sid, "name": name, "created_at": datetime.utcnow().isoformat(), "messages": []}
    _sessions[sid] = session
    return session


def _append_message(session_id: str, role: str, content: Any) -> dict:
    msg = {"id": str(uuid.uuid4()), "role": role, "content": content, "ts": datetime.utcnow().isoformat()}
    if session_id in _sessions:
        _sessions[session_id]["messages"].append(msg)
    return msg


# ---------------------------------------------------------------------------
# SDK client factory — builds a synthgen.Client from user-supplied params
# ---------------------------------------------------------------------------

def _make_client(backend: str, api_key: str | None, model: str | None = None):
    """Build a synthgen Client. Imports lazily so missing extras fail clearly."""
    if backend == "anthropic":
        try:
            from synthgen.backends import AnthropicBackend
        except ImportError as e:
            raise RuntimeError("Install anthropic extra: pip install 'synthgen[anthropic]'") from e
        kwargs: dict[str, Any] = {}
        if api_key:
            kwargs["api_key"] = api_key
        if model:
            kwargs["model"] = model
        be = AnthropicBackend(**kwargs)
    elif backend == "gemini":
        try:
            from synthgen.backends import GeminiBackend
        except ImportError as e:
            raise RuntimeError("Install gemini extra: pip install 'synthgen[gemini]'") from e
        kwargs = {}
        if api_key:
            kwargs["api_key"] = api_key
        if model:
            kwargs["model"] = model
        be = GeminiBackend(**kwargs)
    else:
        raise ValueError(f"Unknown backend {backend!r}. Supported: anthropic, gemini.")

    from synthgen import Client
    return Client(backend=be)


# ---------------------------------------------------------------------------
# Sink factory — builds the right sink from connector config dict
# ---------------------------------------------------------------------------

def _make_sink(connector: dict[str, Any]):
    """
    connector examples:
      { "type": "public-api", "url": "...", "auth_type": "none", "data_format": "json" }
      { "type": "hivemq",     "host": "...", "port": 8883, "username": "...", "password": "...", "topic": "synthgen/stream" }
      { "type": "snowflake",  "account": "...", "user": "...", "password": "...", "warehouse": "...", "database": "..." }
      { "type": "databricks", "host": "...", "token": "...", "http_path": "..." }
    """
    t = connector.get("type", "")

    if t == "public-api":
        from synthgen.sinks import PublicAPISink
        return PublicAPISink(
            url=connector["url"],
            auth_type=connector.get("auth_type", "none"),
            auth_value=connector.get("auth_value"),
            data_format=connector.get("data_format", "json"),
            custom_headers=connector.get("custom_headers"),
        )

    if t == "hivemq":
        from synthgen.sinks import HiveMQSink
        return HiveMQSink(
            host=connector["host"],
            port=int(connector.get("port", 8883)),
            username=connector["username"],
            password=connector["password"],
            topic=connector.get("topic", "synthgen/stream"),
            qos=connector.get("qos", 1),
        )

    if t == "snowflake":
        from synthgen.sinks import SnowflakeSink
        return SnowflakeSink(
            account=connector["account"],
            user=connector["user"],
            password=connector.get("password"),
            warehouse=connector["warehouse"],
            database=connector["database"],
            schema=connector.get("schema", "SYNTHGEN"),
            table=connector.get("table", "SYNTHGEN_STREAM"),
            batch_size=connector.get("batch_size", 10),
        )

    if t == "databricks":
        from synthgen.sinks import DatabricksSink
        return DatabricksSink(
            host=connector["host"],
            token=connector["token"],
            http_path=connector["http_path"],
            catalog=connector.get("catalog", "hive_metastore"),
            schema=connector.get("schema", "synthgen"),
            table=connector.get("table", "synthgen_stream"),
            batch_size=connector.get("batch_size", 10),
        )

    raise ValueError(f"Unknown connector type {t!r}. Supported: public-api, hivemq, snowflake, databricks.")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    prompt: str
    count: int = Field(default=100, ge=1, le=200)
    backend: str = Field(default="gemini")
    api_key: str | None = None
    model: str | None = None
    seed: int | None = None
    correlation_mode: str = "auto"
    session_id: str | None = None        # if set, message is saved to session


class ConnectorTestRequest(BaseModel):
    connector: dict[str, Any]


class SessionCreateRequest(BaseModel):
    name: str = "New session"


class SessionRenameRequest(BaseModel):
    name: str


class MessageRequest(BaseModel):
    role: str           # "user" | "assistant"
    content: Any        # string or dict


# ---------------------------------------------------------------------------
# Routes — health
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "vdf-api"}


# ---------------------------------------------------------------------------
# Routes — batch generation
# ---------------------------------------------------------------------------

@app.post("/api/generate")
def generate(req: GenerateRequest):
    """Generate a batch of synthetic records and return them as a JSON array."""
    try:
        client = _make_client(req.backend, req.api_key, req.model)
        records = client.generate(
            req.prompt,
            count=req.count,
            seed=req.seed,
            correlation_mode=req.correlation_mode,
        )
        result = {"records": records, "count": len(records), "prompt": req.prompt}

        # Persist to session if requested
        if req.session_id:
            _append_message(req.session_id, "user", req.prompt)
            _append_message(req.session_id, "assistant", result)

        return result

    except Exception as exc:
        _logger.exception("Generate failed")
        return {"error": str(exc)}, 500


# ---------------------------------------------------------------------------
# Routes — connector test
# ---------------------------------------------------------------------------

@app.post("/api/connectors/test")
def test_connector(req: ConnectorTestRequest):
    """
    Open the sink, send one dummy record, close it.
    Returns { "ok": true } or { "ok": false, "error": "..." }.
    """
    try:
        sink = _make_sink(req.connector)
        dummy = {"_test": True, "ts": datetime.utcnow().isoformat()}
        sink.open()
        sink.write(dummy)
        sink.close()
        return {"ok": True}
    except Exception as exc:
        _logger.warning("Connector test failed: %s", exc)
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Routes — sessions
# ---------------------------------------------------------------------------

@app.get("/api/sessions")
def list_sessions():
    return {"sessions": [{"id": s["id"], "name": s["name"], "created_at": s["created_at"], "message_count": len(s["messages"])} for s in _sessions.values()]}


@app.post("/api/sessions")
def create_session(req: SessionCreateRequest):
    return _new_session(req.name)


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    if session_id not in _sessions:
        return {"error": "Session not found"}, 404
    return _sessions[session_id]


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str):
    if session_id not in _sessions:
        return {"error": "Session not found"}, 404
    del _sessions[session_id]
    return {"deleted": session_id}


@app.put("/api/sessions/{session_id}")
def rename_session(session_id: str, req: SessionRenameRequest):
    if session_id not in _sessions:
        return {"error": "Session not found"}, 404
    _sessions[session_id]["name"] = req.name
    return _sessions[session_id]


@app.post("/api/sessions/{session_id}/messages")
def add_message(session_id: str, req: MessageRequest):
    if session_id not in _sessions:
        return {"error": "Session not found"}, 404
    return _append_message(session_id, req.role, req.content)


# ---------------------------------------------------------------------------
# WebSocket — streaming
# ---------------------------------------------------------------------------

@app.websocket("/api/ws/stream")
async def ws_stream(websocket: WebSocket):
    """
    WebSocket endpoint for live record streaming.

    1. Client sends one JSON config message.
    2. Server streams records one by one.
    3. Client can send { "action": "stop" } at any time to cancel.
    4. Server sends { "type": "done", "total": N } when finished.

    Config message fields:
        prompt          str       required
        backend         str       "anthropic" | "gemini"
        api_key         str|null  override env var
        model           str|null  model ID override
        interval_sec    float     seconds between records (default 1)
        duration_sec    int|null  stop after N seconds (null = run until stop)
        correlation_mode str      "auto" | "independent" | "derived" | "multivariate"
        connector       dict|null sink config (see _make_sink docstring)
        session_id      str|null  save conversation to session
    """
    await websocket.accept()
    _logger.info("WebSocket connected: %s", websocket.client)

    stop_event = threading.Event()   # signals background thread to stop
    loop = asyncio.get_event_loop()  # for thread-safe send

    async def _send(msg: dict):
        """Send JSON message to client safely."""
        try:
            await websocket.send_text(json.dumps(msg, default=str))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Receive config
    # ------------------------------------------------------------------
    try:
        raw = await websocket.receive_text()
        cfg = json.loads(raw)
    except Exception as exc:
        await _send({"type": "error", "message": f"Invalid config: {exc}"})
        await websocket.close()
        return

    prompt         = cfg.get("prompt", "")
    backend        = cfg.get("backend", "gemini")
    api_key        = cfg.get("api_key")
    model          = cfg.get("model")
    interval_sec   = float(cfg.get("interval_sec", 1.0))
    duration_sec   = cfg.get("duration_sec")           # None = unbounded
    correlation    = cfg.get("correlation_mode", "auto")
    connector_cfg  = cfg.get("connector")              # None = no sink
    session_id     = cfg.get("session_id")

    if not prompt:
        await _send({"type": "error", "message": "prompt is required"})
        await websocket.close()
        return

    # Save user message to session
    if session_id:
        _append_message(session_id, "user", prompt)

    # ------------------------------------------------------------------
    # Build client + optional sink
    # ------------------------------------------------------------------
    try:
        client = _make_client(backend, api_key, model)
        sink   = _make_sink(connector_cfg) if connector_cfg else None
    except Exception as exc:
        await _send({"type": "error", "message": str(exc)})
        await websocket.close()
        return

    await _send({"type": "status", "message": f"Compiling spec for: {prompt!r}"})

    # ------------------------------------------------------------------
    # Stream in a background thread (SDK is synchronous)
    # ------------------------------------------------------------------
    total_sent = 0

    def _stream_thread():
        nonlocal total_sent
        try:
            if sink:
                sink.open()

            for record in client.stream(
                prompt,
                interval_sec=interval_sec,
                duration_sec=duration_sec,
                correlation_mode=correlation,
            ):
                if stop_event.is_set():
                    break

                if sink:
                    sink.write(record)

                total_sent += 1
                # Send record to WebSocket from thread
                asyncio.run_coroutine_threadsafe(
                    _send({"type": "record", "data": record, "index": total_sent}),
                    loop,
                ).result(timeout=5)

        except Exception as exc:
            asyncio.run_coroutine_threadsafe(
                _send({"type": "error", "message": str(exc)}),
                loop,
            ).result(timeout=5)
        finally:
            if sink:
                try:
                    sink.close()
                except Exception:
                    pass
            asyncio.run_coroutine_threadsafe(
                _send({"type": "done", "total": total_sent}),
                loop,
            ).result(timeout=5)

    thread = threading.Thread(target=_stream_thread, daemon=True)
    thread.start()

    # ------------------------------------------------------------------
    # Listen for stop signal from client while streaming
    # ------------------------------------------------------------------
    try:
        while thread.is_alive():
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=0.5)
                data = json.loads(msg)
                if data.get("action") == "stop":
                    _logger.info("Stop signal received from client")
                    stop_event.set()
                    break
            except asyncio.TimeoutError:
                continue
            except WebSocketDisconnect:
                _logger.info("WebSocket disconnected by client")
                stop_event.set()
                break
    except Exception:
        stop_event.set()

    thread.join(timeout=10)

    # Save assistant summary to session
    if session_id:
        _append_message(session_id, "assistant", {
            "type": "stream_result",
            "prompt": prompt,
            "total_records": total_sent,
            "connector": connector_cfg.get("type") if connector_cfg else None,
        })

    _logger.info("WebSocket stream finished. Total: %d records", total_sent)


# ---------------------------------------------------------------------------
# Run directly
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8001, reload=True)
