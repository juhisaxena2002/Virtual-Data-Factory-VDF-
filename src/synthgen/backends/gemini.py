"""Gemini backend.

Uses Google's ``google-genai`` SDK to call Gemini models with **function
calling** forced. The function declaration synthgen passes is the
``emit_spec`` function — when Gemini calls it, the function arguments
*are* the spec dict synthgen needs.

Auth:
    Pass ``api_key`` directly, or set ``GOOGLE_API_KEY`` / ``GEMINI_API_KEY``
    in the environment and the SDK will pick it up.

Model defaults:
    ``gemini-2.5-flash`` — fast, cheap, supports function calling
    natively. Override via the ``model`` kwarg.
"""

from __future__ import annotations

import os
from typing import Any

from ..errors import BackendError, BackendResponseError


class GeminiBackend:
    """LLM backend using Google Gemini.

    Parameters
    ----------
    api_key
        Gemini API key. If ``None``, reads from ``GOOGLE_API_KEY`` or
        ``GEMINI_API_KEY``.
    model
        Gemini model ID. Defaults to ``gemini-2.5-flash``.
    temperature
        Sampling temperature. Defaults to 0.2 for consistency.
    max_output_tokens
        Cap on output tokens. Defaults to 2048.
    """

    name = "gemini"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-2.5-flash",
        temperature: float = 0.2,
        max_output_tokens: int = 2048,
    ) -> None:
        # Import lazily so users who pass a different backend don't pay
        # the import cost (and don't need google-genai installed if they
        # ever bring a different backend in).
        try:
            from google import genai
        except ImportError as e:
            raise BackendError(
                "GeminiBackend requires the google-genai package. "
                "Install with: pip install google-genai"
            ) from e

        resolved_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not resolved_key:
            raise BackendError(
                "No Gemini API key provided. Pass api_key=... or set "
                "GOOGLE_API_KEY / GEMINI_API_KEY in the environment."
            )

        self._client = genai.Client(api_key=resolved_key)
        self._model = model
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens

    def supports_tool_use(self) -> bool:
        """Gemini supports native function calling."""
        return True

    # -------------------------------------------------------------------
    # Tool translation
    # -------------------------------------------------------------------
    @staticmethod
    def _to_gemini_function(tool: dict[str, Any]) -> dict[str, Any]:
        """Convert synthgen's tool format to Gemini's function declaration.

        Synthgen tools follow the Anthropic shape:
            {"name": ..., "description": ..., "input_schema": {...}}
        Gemini wants:
            {"name": ..., "description": ..., "parameters": {...}}
        Plus Gemini doesn't allow ``additionalProperties`` or ``$schema``
        keys in the schema — they need to be stripped recursively.
        """
        parameters = _clean_schema_for_gemini(tool["input_schema"])
        return {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": parameters,
        }

    # -------------------------------------------------------------------
    # Main entry point
    # -------------------------------------------------------------------
    def compile_spec(
        self,
        prompt: str,
        *,
        system_prompt: str,
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Call Gemini and extract the emit_spec function-call args."""
        from google.genai import types as gtypes

        # Build Gemini's function declarations.
        function_declarations = [self._to_gemini_function(t) for t in tools]

        gemini_tools = [gtypes.Tool(function_declarations=function_declarations)]

        # Force the model to call emit_spec — the equivalent of
        # Anthropic's tool_choice="emit_spec".
        tool_config = gtypes.ToolConfig(
            function_calling_config=gtypes.FunctionCallingConfig(
                mode="ANY",
                allowed_function_names=["emit_spec"],
            )
        )

        config = gtypes.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=self._temperature,
            max_output_tokens=self._max_output_tokens,
            tools=gemini_tools,
            tool_config=tool_config,
        )

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=config,
            )
        except Exception as e:
            raise BackendError(f"Gemini API call failed: {e}", raw=e) from e

        # Extract the function call. Gemini may return multiple parts;
        # we want the first function_call whose name is emit_spec.
        try:
            candidates = response.candidates or []
            for candidate in candidates:
                content = getattr(candidate, "content", None)
                if not content:
                    continue
                for part in getattr(content, "parts", []) or []:
                    fn_call = getattr(part, "function_call", None)
                    if fn_call and fn_call.name == "emit_spec":
                        # args is a dict-like proto Map. Convert to plain dict.
                        args = dict(fn_call.args) if fn_call.args else {}
                        return _normalize_proto_dict(args)
        except Exception as e:
            raise BackendResponseError(
                f"Failed to parse Gemini response: {e}"
            ) from e

        raise BackendResponseError(
            "Gemini did not return an emit_spec function call. "
            f"Got response: {response!r}"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _clean_schema_for_gemini(schema: dict[str, Any]) -> dict[str, Any]:
    """Strip keys Gemini's schema parser doesn't accept.

    Gemini's Schema proto accepts a subset of JSON Schema. The keys we
    need to remove or transform include:
      * ``$schema``, ``$defs``, ``$ref`` — Gemini doesn't resolve refs
      * ``additionalProperties`` — not supported
      * ``minLength``, ``maxLength`` — accepted on string only
      * ``pattern`` — accepted on string only
      * ``const`` — not supported

    We also inline ``$ref`` references by walking the original schema.
    """
    # Inline refs first.
    defs = schema.get("$defs", {})
    inlined = _inline_refs(schema, defs)

    # Then strip unsupported keys.
    return _strip_unsupported_keys(inlined)


def _inline_refs(node: Any, defs: dict[str, Any]) -> Any:
    """Recursively replace ``$ref`` nodes with the referenced definition."""
    if isinstance(node, dict):
        if "$ref" in node and len(node) == 1:
            ref = node["$ref"]
            # We only support local refs of the form "#/$defs/Name"
            if ref.startswith("#/$defs/"):
                name = ref.split("/")[-1]
                return _inline_refs(defs[name], defs)
            return node
        return {k: _inline_refs(v, defs) for k, v in node.items() if k != "$defs"}
    if isinstance(node, list):
        return [_inline_refs(item, defs) for item in node]
    return node


_UNSUPPORTED_KEYS = frozenset({
    "$schema", "$id", "$defs", "$ref",
    "additionalProperties",
    "const",
})


def _strip_unsupported_keys(node: Any) -> Any:
    """Remove keys Gemini's schema parser rejects."""
    if isinstance(node, dict):
        return {
            k: _strip_unsupported_keys(v)
            for k, v in node.items()
            if k not in _UNSUPPORTED_KEYS
        }
    if isinstance(node, list):
        return [_strip_unsupported_keys(item) for item in node]
    return node


def _normalize_proto_dict(obj: Any) -> Any:
    """Convert proto Map/RepeatedComposite to plain Python dict/list.

    The google-genai SDK returns ``MapComposite`` objects that act like
    dicts but aren't. Downstream code (JSON Schema validation, generator)
    expects plain dicts/lists, so we recursively convert.
    """
    if hasattr(obj, "items") and not isinstance(obj, dict):
        return {k: _normalize_proto_dict(v) for k, v in obj.items()}
    if isinstance(obj, dict):
        return {k: _normalize_proto_dict(v) for k, v in obj.items()}
    if isinstance(obj, list) or (hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes))):
        try:
            return [_normalize_proto_dict(item) for item in obj]
        except TypeError:
            return obj
    return obj
