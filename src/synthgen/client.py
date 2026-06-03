"""The :class:`Client` class — synthgen's public face.

Users construct a ``Client`` with a backend, then call ``generate``,
``stream``, or ``compile_spec``. All business logic is in private
modules (``_schema``, ``_generator``, ``_stream``); this class just
composes them.
"""

from __future__ import annotations

import json
import logging
from functools import cached_property
from pathlib import Path
from typing import Any, Iterator

from . import _generator, _schema, _stream
from ._spec_cache import SpecCache
from .backends.base import Backend
from .types import DerivedCorrelation, MultivariateCorrelation, Record, Spec

_PROMPTS_DIR = Path(__file__).parent / "prompts"

_logger = logging.getLogger(__name__)

_CORRELATION_MODES = ("auto", "independent", "derived", "multivariate")


def _filter_correlations(spec: Spec, mode: str) -> Spec:
    """Return a copy of ``spec`` with ``correlations`` filtered by mode.

    * ``auto`` — pass through, whatever the LLM emitted.
    * ``independent`` — drop all correlations; fields sampled independently.
    * ``derived`` — keep only derived entries.
    * ``multivariate`` — keep only multivariate entries.

    The filter applies after the cache is consulted/populated, so the
    cache always stores the LLM's original output and the same prompt
    can be replayed under different correlation modes without re-calling
    the LLM.
    """
    if mode == "auto":
        return spec
    if mode == "independent":
        return spec.with_correlations(())
    if mode == "derived":
        return spec.with_correlations(
            tuple(c for c in spec.correlations if isinstance(c, DerivedCorrelation))
        )
    if mode == "multivariate":
        return spec.with_correlations(
            tuple(c for c in spec.correlations if isinstance(c, MultivariateCorrelation))
        )
    raise ValueError(
        f"Unknown correlation mode: {mode!r}. Expected one of {_CORRELATION_MODES}."
    )


class Client:
    """The synthgen SDK's main user-facing class.

    Parameters
    ----------
    backend
        An LLM backend. **Required** in Phase 1 — pass an instance of
        ``GeminiBackend`` (or ``MockBackend`` in tests). No silent default.
    max_row_cap
        Hard cap on the number of rows :meth:`generate` will produce.
        Defaults to 200 (the Phase 1 limit).
    cache
        Semantic prompt → Spec cache. Defaults to ``True`` — the Client
        auto-creates a default :class:`SpecCache` (Chroma persistent +
        MiniLM embedder) and consults it before every LLM call. Pass a
        pre-configured :class:`SpecCache` to override defaults, or
        ``False`` / ``None`` to disable caching entirely.

    Examples
    --------
    >>> from synthgen import Client
    >>> from synthgen.backends import GeminiBackend
    >>> client = Client(backend=GeminiBackend())              # cache on
    >>> records = client.generate("50 fake e-commerce orders", count=50)
    >>> bare = Client(backend=GeminiBackend(), cache=None)    # cache off
    """

    def __init__(
        self,
        backend: Backend,
        max_row_cap: int = 200,
        cache: bool | SpecCache | None = True,
    ) -> None:
        if backend is None:
            raise TypeError(
                "Client requires a backend. Construct one with: "
                "Client(backend=GeminiBackend(api_key=...))"
            )
        self._backend = backend
        self._max_row_cap = max_row_cap
        if cache is True:
            self._cache: SpecCache | None = SpecCache()
        elif isinstance(cache, SpecCache):
            self._cache = cache
        else:
            self._cache = None

    # ------------------------------------------------------------------
    # Lazy prompt loading
    # ------------------------------------------------------------------
    @cached_property
    def _system_prompt(self) -> str:
        """Assemble system prompt + few-shot examples."""
        system = (_PROMPTS_DIR / "system.md").read_text(encoding="utf-8")
        examples = json.loads((_PROMPTS_DIR / "examples.json").read_text(encoding="utf-8"))

        # Append examples to the system prompt so they live in the
        # instruction context rather than the user-turn history.
        example_blocks: list[str] = []
        for ex in examples:
            example_blocks.append(
                f'\nExample user prompt: "{ex["user_prompt"]}"\n'
                f"You would emit_spec with these arguments:\n"
                f"{json.dumps(ex['spec'], indent=2)}\n"
            )
        return system + "\n# Examples\n" + "".join(example_blocks)

    @cached_property
    def _tools(self) -> list[dict[str, Any]]:
        """Load the tool definition (function schema)."""
        return json.loads((_PROMPTS_DIR / "tools.json").read_text(encoding="utf-8"))

    # ------------------------------------------------------------------
    # Prompt → Spec
    # ------------------------------------------------------------------
    def compile_spec(
        self,
        prompt: str,
        *,
        use_cache: bool = True,
        correlation_mode: str = "auto",
    ) -> Spec:
        """Translate a natural-language prompt into a validated :class:`Spec`.

        Useful for inspecting / modifying the spec before generation. The
        returned spec is fully typed and immutable; use
        :meth:`Spec.with_count` to produce a modified copy.

        When the Client was constructed with a cache, a semantic lookup
        is performed first and the backend call is skipped on a hit.
        Pass ``use_cache=False`` to force a fresh LLM call.

        ``correlation_mode`` filters whatever correlations the LLM
        emitted: ``"auto"`` keeps them as-is, ``"independent"`` strips
        them all, ``"derived"`` / ``"multivariate"`` keep only that
        mode. The filter is applied AFTER cache lookup, so the same
        prompt can be replayed under different modes without re-calling
        the LLM.
        """
        cache = self._cache if use_cache else None
        if cache is not None:
            hit = cache.get(prompt)
            if hit is not None:
                pct = (cache.last_similarity or 1.0) * 100.0
                _logger.info(
                    "cache hit: %.1f%% match in vector DB - reusing spec, "
                    "skipping LLM call",
                    pct,
                )
                return _filter_correlations(hit, correlation_mode)
            _logger.info(
                "cache miss: no similar prompt in vector DB - calling %s LLM",
                self._backend.name,
            )

        raw = self._backend.compile_spec(
            prompt,
            system_prompt=self._system_prompt,
            tools=self._tools,
        )
        spec = _schema.validate_spec(raw, self._max_row_cap)
        if cache is not None:
            cache.put(prompt, spec)
        return _filter_correlations(spec, correlation_mode)

    # ------------------------------------------------------------------
    # Batch generation
    # ------------------------------------------------------------------
    def generate(
        self,
        prompt: str,
        count: int = 100,
        seed: int | None = None,
        *,
        use_cache: bool = True,
        correlation_mode: str = "auto",
    ) -> list[Record]:
        """One-shot generation. Compiles spec, generates records, returns list.

        Hard-capped at ``max_row_cap`` (default 200). If ``count`` exceeds
        the cap, it is silently clamped — the LLM's count is *also* clamped.
        """
        spec = self.compile_spec(
            prompt, use_cache=use_cache, correlation_mode=correlation_mode,
        )
        spec = spec.with_count(min(count, self._max_row_cap))
        return _generator.generate(spec, seed=seed)

    def generate_from_spec(
        self,
        spec: Spec,
        count: int | None = None,
        seed: int | None = None,
    ) -> list[Record]:
        """Generate from a pre-existing spec. Skips the LLM call entirely.

        Useful for hand-crafted specs and for replaying saved specs in
        tests or CI.
        """
        if count is not None:
            spec = spec.with_count(min(count, self._max_row_cap))
        return _generator.generate(spec, seed=seed)

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------
    def stream(
        self,
        prompt: str,
        *,
        interval_sec: float | None = None,
        duration_sec: int | None = None,
        seed: int | None = None,
        use_cache: bool = True,
        correlation_mode: str = "auto",
    ) -> Iterator[Record]:
        """Yield records lazily, one every ``interval_sec`` seconds.

        The interval is resolved by precedence: an explicit
        ``interval_sec`` argument wins; otherwise a cadence the prompt
        mentioned (carried on the spec); otherwise the default of one
        record every 5 seconds.

        The iterator terminates after ``duration_sec`` (if set) or runs
        unbounded otherwise. Sink-agnostic — the caller decides what to
        do with each record (publish to MQTT, append to a file, etc.).
        """
        spec = self.compile_spec(
            prompt, use_cache=use_cache, correlation_mode=correlation_mode,
        )
        return self._stream_spec(spec, interval_sec, duration_sec, seed)

    def stream_from_spec(
        self,
        spec: Spec,
        *,
        interval_sec: float | None = None,
        duration_sec: int | None = None,
        seed: int | None = None,
    ) -> Iterator[Record]:
        """Like :meth:`stream`, but from a pre-existing spec — no LLM call."""
        return self._stream_spec(spec, interval_sec, duration_sec, seed)

    def _stream_spec(
        self,
        spec: Spec,
        interval_sec: float | None,
        duration_sec: int | None,
        seed: int | None,
    ) -> Iterator[Record]:
        interval, source = _stream.resolve_stream_interval(
            interval_sec, spec.stream_interval_sec,
        )
        if interval <= 0:
            raise ValueError(
                f"stream interval must be > 0 seconds, got {interval}"
            )
        _logger.info("streaming 1 record every %gs (%s)", interval, source)
        return _stream.rate_limited_iterator(
            spec, rate_per_sec=1.0 / interval, duration_sec=duration_sec, seed=seed,
        )

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    @property
    def backend_name(self) -> str:
        """Name of the active backend (e.g. ``"gemini"``, ``"mock"``)."""
        return self._backend.name
