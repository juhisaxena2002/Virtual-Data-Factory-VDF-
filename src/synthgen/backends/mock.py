"""Mock backend for tests.

Returns canned spec dicts based on the prompt. Critical infrastructure:
because the backend is swappable, every generator/anomaly/client test
can use this instead of hitting Gemini, which means:

* Tests are fast (no network).
* Tests are free (no LLM tokens).
* Tests are deterministic (no model variance).
* Tests work offline (no API key needed).

Real Gemini calls only happen in tests marked ``@pytest.mark.integration``.
"""

from __future__ import annotations

from typing import Any

from ..errors import BackendError, BackendResponseError


class MockBackend:
    """Test fixture backend.

    Construct with a mapping of ``prompt -> spec_dict``. Optionally pass
    ``default`` to return the same spec for any prompt not in the map.
    """

    name = "mock"

    def __init__(
        self,
        responses: dict[str, dict[str, Any]] | None = None,
        default: dict[str, Any] | None = None,
        raise_on: dict[str, Exception] | None = None,
    ) -> None:
        self.responses: dict[str, dict[str, Any]] = responses or {}
        self.default: dict[str, Any] | None = default
        self.raise_on: dict[str, Exception] = raise_on or {}
        # Inspection — tests can assert on what was called.
        self.calls: list[dict[str, Any]] = []

    def supports_tool_use(self) -> bool:
        return True

    def compile_spec(
        self,
        prompt: str,
        *,
        system_prompt: str,
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self.calls.append(
            {"prompt": prompt, "system_prompt": system_prompt, "tools": tools}
        )

        # Test-induced failures.
        if prompt in self.raise_on:
            raise self.raise_on[prompt]

        # Canned response.
        if prompt in self.responses:
            return self.responses[prompt]

        if self.default is not None:
            return self.default

        raise BackendResponseError(
            f"MockBackend has no canned response for prompt: {prompt!r}"
        )
