"""Backend protocol.

A backend is anything with ``compile_spec``, ``supports_tool_use``, and a
``name``. Using a ``Protocol`` instead of an ABC means user-defined
backends don't need to inherit anything — they just need to look right
at the type-checker level.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Backend(Protocol):
    """The contract every LLM backend implements.

    Backends translate a free-form prompt into a structured spec dict.
    Everything downstream — validation, generation, anomalies — is
    backend-agnostic.

    Implementations must:

    * Set a string ``name`` attribute (used in logs / errors).
    * Raise :class:`synthgen.BackendError` for transport-level failures.
    * Raise :class:`synthgen.BackendResponseError` when the response is
      structurally usable but doesn't contain a spec (e.g. model refused,
      missing tool block).
    """

    name: str

    def compile_spec(
        self,
        prompt: str,
        *,
        system_prompt: str,
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Send the prompt + tools to the LLM and return the spec dict.

        Parameters
        ----------
        prompt
            The user's natural-language request.
        system_prompt
            The system / instruction prompt — sets the role and rules.
        tools
            Tool / function-call schemas, in synthgen's canonical
            ``input_schema`` form. Backends adapt these to whatever
            their provider expects.

        Returns
        -------
        dict
            The raw spec dict, before JSON Schema validation.
            (Validation happens in :mod:`synthgen._schema`.)
        """
        ...

    def supports_tool_use(self) -> bool:
        """Whether this backend can natively force structured tool output.

        Backends that return ``False`` (e.g. local Llama models) signal
        that synthgen should fall back to JSON-mode prompting.
        """
        ...
