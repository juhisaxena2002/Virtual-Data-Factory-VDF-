"""Exception hierarchy for synthgen.

All synthgen exceptions inherit from :class:`SynthgenError`. Each carries
an :attr:`exit_code` so the CLI can map errors to shell exit codes.
"""

from __future__ import annotations

from typing import Any


class SynthgenError(Exception):
    """Base class for all synthgen exceptions."""

    exit_code: int = 1


class BackendError(SynthgenError):
    """Transport-level failure calling the LLM provider.

    Covers network failures, auth failures, throttling, and timeouts.
    The original provider exception is preserved as ``__cause__``.
    """

    exit_code = 1

    def __init__(self, message: str, raw: Any = None) -> None:
        super().__init__(message)
        self.raw = raw


class BackendResponseError(SynthgenError):
    """The LLM responded, but the response is unusable.

    Examples: missing tool/function block, malformed JSON, model refusal.
    Typically retry with a different model or surface to the user.
    """

    exit_code = 1


class SpecValidationError(SynthgenError):
    """The spec returned by the LLM failed JSON Schema validation."""

    exit_code = 2

    def __init__(self, message: str, errors: list[Any] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or []


class GenerationError(SynthgenError):
    """The generator failed to produce records from a valid spec.

    Indicates a bug — should never happen in normal use. If you see one,
    file a bug report with the spec that triggered it.
    """

    exit_code = 3
