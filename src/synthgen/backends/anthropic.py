"""Anthropic Claude backend.

Uses Anthropic's official ``anthropic`` SDK to call Claude with tool use
forced. Since synthgen's internal tool definition is already in the
Anthropic-native shape (``name`` + ``description`` + ``input_schema``),
no schema translation is needed — we pass tools through as-is.

Auth:
    Pass ``api_key`` directly, or set ``ANTHROPIC_API_KEY`` in the
    environment and the SDK will pick it up automatically.

Model defaults:
    ``claude-haiku-4-5`` — fast, cheap, and more than capable for the
    structured spec-generation task synthgen needs. Override via the
    ``model`` kwarg if you need higher quality (``claude-sonnet-4-6``
    or ``claude-opus-4-7``).
"""

from __future__ import annotations

import os
from typing import Any

from ..errors import BackendError, BackendResponseError


class AnthropicBackend:
    """LLM backend using Anthropic's Claude API directly.

    Parameters
    ----------
    api_key
        Anthropic API key. If ``None``, reads from ``ANTHROPIC_API_KEY``.
    model
        Claude model ID. Defaults to ``claude-haiku-4-5`` — cheap and
        plenty capable for spec compilation. Use ``claude-sonnet-4-6``
        or ``claude-opus-4-7`` for harder prompts.
    temperature
        Sampling temperature. Defaults to 0.2 for consistency.
    max_tokens
        Cap on output tokens. Defaults to 2048 — plenty for a spec dict.
    """

    name = "anthropic"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-haiku-4-5",
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> None:
        # Lazy import so users on other backends don't need anthropic installed.
        try:
            import anthropic
        except ImportError as e:
            raise BackendError(
                "AnthropicBackend requires the anthropic package. "
                "Install with: pip install anthropic"
            ) from e

        resolved_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not resolved_key:
            raise BackendError(
                "No Anthropic API key provided. Pass api_key=... or set "
                "ANTHROPIC_API_KEY in the environment. "
                "Get a key at https://console.anthropic.com/"
            )

        self._client = anthropic.Anthropic(api_key=resolved_key)
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    def supports_tool_use(self) -> bool:
        """Claude has native tool use."""
        return True

    def compile_spec(
        self,
        prompt: str,
        *,
        system_prompt: str,
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Call Claude and extract the emit_spec tool_use arguments.

        Synthgen's tool definitions are already in Anthropic's shape
        (``name``, ``description``, ``input_schema``) so we pass them
        through without translation.
        """
        try:
            import anthropic   # for the typed exception
            message = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                system=system_prompt,
                tools=tools,
                # Force Claude to call emit_spec — equivalent to function
                # calling with allowed_function_names in Gemini.
                tool_choice={"type": "tool", "name": "emit_spec"},
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.APIError as e:
            raise BackendError(f"Anthropic API call failed: {e}", raw=e) from e
        except Exception as e:
            # Network failure, timeout, auth issue, etc.
            raise BackendError(f"Anthropic call failed: {e}", raw=e) from e

        # Walk Claude's response content for the emit_spec tool_use block.
        # Claude may return multiple content blocks (text + tool_use); we
        # want the first tool_use whose name is emit_spec.
        for block in message.content:
            if getattr(block, "type", None) == "tool_use" and block.name == "emit_spec":
                # block.input is already a plain dict — no proto-conversion
                # needed, unlike Gemini.
                return dict(block.input)

        raise BackendResponseError(
            "Claude did not return an emit_spec tool_use block. "
            f"Stop reason: {message.stop_reason!r}. "
            f"Content blocks: {[getattr(b, 'type', '?') for b in message.content]}"
        )
