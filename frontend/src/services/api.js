/**
 * api.js — All FastAPI backend calls in one place.
 * Base URL is proxied via package.json proxy to http://localhost:8000
 */

const BASE = "/api";

// ─── helpers ────────────────────────────────────────────────────────────────

async function post(path, body) {
  console.log(`[API] POST ${path}`, body);
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  console.log(`[API] POST ${path} →`, data);
  return data;
}

async function get(path) {
  console.log(`[API] GET ${path}`);
  const res = await fetch(`${BASE}${path}`);
  const data = await res.json();
  console.log(`[API] GET ${path} →`, data);
  return data;
}

async function del(path) {
  console.log(`[API] DELETE ${path}`);
  const res = await fetch(`${BASE}${path}`, { method: "DELETE" });
  return res.json();
}

async function put(path, body) {
  console.log(`[API] PUT ${path}`, body);
  const res = await fetch(`${BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

// ─── health ─────────────────────────────────────────────────────────────────

export const checkHealth = () => get("/health");

// ─── generation ─────────────────────────────────────────────────────────────

/**
 * Batch generate records.
 * @param {string} prompt
 * @param {object} config  { backend, api_key, count }
 * @returns {Promise<{records: object[], count: number, prompt: string}>}
 */
export const generateBatch = (prompt, config) =>
  post("/generate", {
    prompt,
    backend: config.backend,
    api_key: config.apiKey,
    count: config.count ?? 10,
  });

// ─── connectors ─────────────────────────────────────────────────────────────

/**
 * Test a connector config.
 * @param {object} connector  { type, ...fields }
 * @returns {Promise<{ok: boolean, error?: string}>}
 */
export const testConnector = (connector) =>
  post("/connectors/test", { connector });

// ─── sessions ───────────────────────────────────────────────────────────────

export const listSessions    = ()          => get("/sessions");
export const createSession   = (name)      => post("/sessions", { name });
export const getSession      = (id)        => get(`/sessions/${id}`);
export const deleteSession   = (id)        => del(`/sessions/${id}`);
export const renameSession   = (id, name)  => put(`/sessions/${id}`, { name });
export const addMessage      = (id, role, content) =>
  post(`/sessions/${id}/messages`, { role, content });

// ─── websocket streaming ─────────────────────────────────────────────────────

/**
 * Open a WebSocket stream.
 *
 * @param {object} config
 *   prompt, backend, apiKey, intervalSec, durationSec, connector?
 * @param {function} onRecord   called with each { type:"record", data, index }
 * @param {function} onStatus   called with { type:"status", message }
 * @param {function} onDone     called with { type:"done", total }
 * @param {function} onError    called with { type:"error", message }
 * @returns {{ stop: function }}  call stop() to cancel stream
 */
export function openStream(config, { onRecord, onStatus, onDone, onError }) {
  const WS_URL = `ws://localhost:8001/api/ws/stream`;
  console.log("[WS] Opening stream", config);

  const ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    console.log("[WS] Connected — sending config");
    ws.send(
      JSON.stringify({
        prompt:           config.prompt,
        backend:          config.backend,
        api_key:          config.apiKey,
        interval_sec:     config.intervalSec ?? 1,
        duration_sec:     config.durationSec ?? null,
        correlation_mode: "auto",
        connector:        config.connector ?? null,
        session_id:       config.sessionId ?? null,
      })
    );
  };

  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    console.log("[WS] message →", msg);
    if (msg.type === "record")  onRecord?.(msg);
    if (msg.type === "status")  onStatus?.(msg);
    if (msg.type === "done")    onDone?.(msg);
    if (msg.type === "error")   onError?.(msg);
  };

  ws.onerror = (e) => {
    console.error("[WS] error", e);
    onError?.({ type: "error", message: "WebSocket connection error" });
  };

  ws.onclose = () => console.log("[WS] closed");

  return {
    stop: () => {
      console.log("[WS] Sending stop signal");
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: "stop" }));
      }
      ws.close();
    },
  };
}
