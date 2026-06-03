"""Rate-limited record streaming.

Yields records lazily at ``rate_per_sec``, optionally bounded by
``duration_sec``. Sink-agnostic — the caller decides what to do with
each record (publish to MQTT, append to a file, push to a websocket, …).

This module is intentionally tiny. The hard work is in :mod:`._generator`;
this just paces it.
"""

from __future__ import annotations

import time
from typing import Iterator

from ._generator import generate
from .types import Record, Spec

# Default cadence when neither the prompt nor an explicit override
# specifies one: one record every five seconds.
DEFAULT_STREAM_INTERVAL_SEC = 5.0


def resolve_stream_interval(
    explicit: float | None,
    spec_interval: float | None,
) -> tuple[float, str]:
    """Resolve the streaming interval and report where it came from.

    Precedence: an explicit override (CLI flag / SDK arg) wins, then the
    prompt-derived value carried on the spec, then the default. The
    second element of the return tuple is a human-readable source label
    for logging.
    """
    if explicit is not None:
        return explicit, "explicit override"
    if spec_interval is not None:
        return spec_interval, "prompt"
    return DEFAULT_STREAM_INTERVAL_SEC, "default"


def rate_limited_iterator(
    spec: Spec,
    rate_per_sec: float,
    duration_sec: int | None = None,
    seed: int | None = None,
) -> Iterator[Record]:
    """Yield records at the requested rate.

    Each call to :func:`_generator.generate` produces a batch; the
    iterator yields one record at a time and sleeps the remainder of
    each interval. Cheap and correct for rates up to ~1,000/sec; above
    that, use a dedicated batching strategy.

    Parameters
    ----------
    spec
        Validated spec.
    rate_per_sec
        Records per second. Must be > 0.
    duration_sec
        Optional total duration. If ``None``, the iterator is unbounded
        (the caller is responsible for breaking out of the loop).
    seed
        Optional seed for deterministic streams.
    """
    if rate_per_sec <= 0:
        raise ValueError(f"rate_per_sec must be > 0, got {rate_per_sec}")

    interval = 1.0 / rate_per_sec
    start = time.monotonic()
    next_emit = start
    n_emitted = 0

    # Generate records in small batches to amortize the per-batch fixed costs
    # of seeding/dispatch-building. Batch size = max(rate, 50), capped by
    # spec.count for finite duration_sec.
    batch_size = max(int(rate_per_sec), 50)

    while True:
        # Stop conditions.
        if duration_sec is not None and (time.monotonic() - start) >= duration_sec:
            return

        # Produce a batch — but stay within spec.count if it's set lower.
        # For streaming we ignore spec.count's cap and keep going; the
        # caller's duration_sec bounds the stream.
        batch_spec = spec.with_count(batch_size)
        batch_records = generate(batch_spec, seed=(seed + n_emitted) if seed is not None else None)

        for record in batch_records:
            now = time.monotonic()
            if duration_sec is not None and (now - start) >= duration_sec:
                return
            # Sleep until it's time for this record.
            sleep_for = next_emit - now
            if sleep_for > 0:
                time.sleep(sleep_for)
            yield record
            n_emitted += 1
            next_emit += interval
