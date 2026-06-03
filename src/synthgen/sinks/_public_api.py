"""Public API sink — POST synthgen records to any REST endpoint over HTTP.

This sink is intentionally generic. The user supplies three things:
  - destination URL
  - auth type + credential (bearer token, api key, or none)
  - data format (json or ndjson)

That covers the vast majority of REST-based platforms:
Webhook.site, Elasticsearch, Splunk HEC, Datadog Logs, Supabase, etc.

Usage (SDK)
-----------
::

    from synthgen.sinks import PublicAPISink

    sink = PublicAPISink(
        url="https://webhook.site/your-uuid",
        auth_type="none",
        data_format="json",
    )
    with sink:
        for record in client.stream("IoT sensors", interval_sec=1):
            sink.send(record)

Usage (CLI)
-----------
::

    synthgen "IoT sensors" --stream --backend gemini \\
      --sink public-api \\
      --api-url "https://webhook.site/your-uuid" \\
      --api-auth-type none \\
      --api-format json \\
      --interval 1 --duration 30

Auth types
----------
- ``none``    — no Authorization header
- ``bearer``  — ``Authorization: Bearer <value>``
- ``api_key`` — ``Authorization: ApiKey <value>``

Data formats
------------
- ``json``   — each record POSTed as a JSON object  ``{"field": "value", ...}``
- ``ndjson`` — each record POSTed as a newline-delimited JSON line (Elasticsearch etc.)

Retry behaviour
---------------
One automatic retry on HTTP 5xx with a 1-second backoff.
4xx errors are logged as warnings but not retried (bad config, fix the args).
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

_logger = logging.getLogger(__name__)

_SUPPORTED_AUTH_TYPES = ("none", "bearer", "api_key")
_SUPPORTED_FORMATS = ("json", "ndjson")
_DEFAULT_TIMEOUT = 10       # seconds per request
_RETRY_WAIT = 1.0           # seconds before the single retry on 5xx


class PublicAPISink:
    """POST synthgen records to any REST API endpoint.

    Parameters
    ----------
    url:
        Destination endpoint. Must include the scheme, e.g.
        ``https://webhook.site/abc123`` or
        ``https://my-es.cloud:9243/synthgen/_doc``.
    auth_type:
        ``"none"`` | ``"bearer"`` | ``"api_key"``.
        Default: ``"none"``.
    auth_value:
        The token or key string. Required when ``auth_type`` is not
        ``"none"``. Ignored otherwise.
    data_format:
        ``"json"`` — POST a JSON object per record (default).
        ``"ndjson"`` — POST a newline-terminated JSON line per record
        (required by Elasticsearch ``_doc`` endpoint, Splunk HEC, etc.).
    custom_headers:
        Optional dict of extra headers merged into every request.
        Useful for platform-specific requirements like
        ``{"X-Splunk-Index": "main"}`` or ``{"dd-api-key": "..."}``.
    timeout:
        Per-request timeout in seconds. Default: 10.
    """

    def __init__(
        self,
        url: str,
        auth_type: str = "none",
        auth_value: str | None = None,
        data_format: str = "json",
        custom_headers: dict[str, str] | None = None,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> None:
        if auth_type not in _SUPPORTED_AUTH_TYPES:
            raise ValueError(
                f"auth_type must be one of {_SUPPORTED_AUTH_TYPES}, got {auth_type!r}"
            )
        if data_format not in _SUPPORTED_FORMATS:
            raise ValueError(
                f"data_format must be one of {_SUPPORTED_FORMATS}, got {data_format!r}"
            )
        if auth_type != "none" and not auth_value:
            raise ValueError(
                f"auth_value is required when auth_type is {auth_type!r}"
            )

        self._url = url
        self._auth_type = auth_type
        self._auth_value = auth_value or ""
        self._data_format = data_format
        self._custom_headers = custom_headers or {}
        self._timeout = timeout
        self._session: Any = None          # requests.Session, set in open()
        self._headers: dict[str, str] = {} # built once in open()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def open(self) -> None:
        """Initialise the HTTP session and build static headers."""
        try:
            import requests  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "PublicAPISink requires the 'requests' library. "
                "Install with: pip install requests"
            ) from exc

        self._session = requests.Session()

        # Build headers once — reused for every send()
        headers: dict[str, str] = {"Content-Type": "application/json"}

        if self._auth_type == "bearer":
            headers["Authorization"] = f"Bearer {self._auth_value}"
        elif self._auth_type == "api_key":
            headers["Authorization"] = f"ApiKey {self._auth_value}"

        # Merge custom headers last so user can override Content-Type if needed
        headers.update(self._custom_headers)
        self._headers = headers

        _logger.info(
            "PublicAPISink: ready → %s  auth=%s  format=%s",
            self._url, self._auth_type, self._data_format,
        )

    def write(self, record: dict[str, Any]) -> None:
        """Alias for send() — called by SinkRouter."""
        self.send(record)

    def send(self, record: dict[str, Any]) -> None:
        """POST one record to the destination URL."""
        if self._session is None:
            raise RuntimeError(
                "PublicAPISink.send() called before open(). "
                "Use 'with PublicAPISink(...) as sink:'"
            )

        payload = self._serialize(record)
        self._post_with_retry(payload)

    def close(self) -> None:
        """Close the underlying HTTP session."""
        if self._session is not None:
            self._session.close()
            self._session = None
            _logger.info("PublicAPISink: session closed")

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "PublicAPISink":
        self.open()
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _serialize(self, record: dict[str, Any]) -> bytes:
        """Encode a record to bytes according to the chosen format."""
        if self._data_format == "ndjson":
            # Newline-terminated JSON line — required by ES, Splunk HEC etc.
            return (json.dumps(record, default=str, ensure_ascii=False) + "\n").encode("utf-8")
        # Default: plain JSON object
        return json.dumps(record, default=str, ensure_ascii=False).encode("utf-8")

    def _post_with_retry(self, payload: bytes) -> None:
        """POST payload; one retry on 5xx after a short backoff."""
        for attempt in (1, 2):
            try:
                resp = self._session.post(
                    self._url,
                    data=payload,
                    headers=self._headers,
                    timeout=self._timeout,
                )
            except Exception as exc:
                _logger.warning(
                    "PublicAPISink: request error (attempt %d/2): %s", attempt, exc
                )
                if attempt == 2:
                    raise
                time.sleep(_RETRY_WAIT)
                continue

            if resp.status_code < 300:
                _logger.debug(
                    "PublicAPISink: → %s  %d", self._url, resp.status_code
                )
                return

            if resp.status_code >= 500 and attempt == 1:
                _logger.warning(
                    "PublicAPISink: HTTP %d from %s — retrying in %.1fs",
                    resp.status_code, self._url, _RETRY_WAIT,
                )
                time.sleep(_RETRY_WAIT)
                continue

            # 4xx — bad config, no point retrying
            _logger.warning(
                "PublicAPISink: HTTP %d from %s — check URL / auth / format. "
                "Response: %s",
                resp.status_code, self._url, resp.text[:200],
            )
            return
