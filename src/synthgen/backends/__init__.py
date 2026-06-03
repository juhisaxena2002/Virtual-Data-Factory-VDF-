"""Backend implementations.

A backend is anything that implements the :class:`Backend` protocol —
one method, ``compile_spec(prompt, *, system_prompt, tools) -> dict``.

Ships:

* :class:`AnthropicBackend` — Anthropic Claude via the ``anthropic`` SDK.
* :class:`GeminiBackend` — Google Gemini via the ``google-genai`` SDK.
* :class:`MockBackend` — test fixture returning canned responses.

Future: OpenAI, Azure OpenAI, and Ollama backends behind the same
protocol — no changes to existing user code.
"""
from dotenv import load_dotenv
load_dotenv()
from .anthropic import AnthropicBackend
from .base import Backend
from .gemini import GeminiBackend
from .mock import MockBackend

__all__ = ["Backend", "AnthropicBackend", "GeminiBackend", "MockBackend"]
