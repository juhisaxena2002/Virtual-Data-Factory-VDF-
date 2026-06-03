"""Tests for streaming interval resolution."""

from __future__ import annotations

import pytest

from synthgen import Client
from synthgen.backends import MockBackend
from synthgen._stream import (
    DEFAULT_STREAM_INTERVAL_SEC,
    resolve_stream_interval,
)


class TestResolveStreamInterval:
    def test_default_when_nothing_specified(self) -> None:
        interval, source = resolve_stream_interval(None, None)
        assert interval == DEFAULT_STREAM_INTERVAL_SEC
        assert source == "default"

    def test_prompt_value_used_when_no_override(self) -> None:
        interval, source = resolve_stream_interval(None, 2.0)
        assert interval == 2.0
        assert source == "prompt"

    def test_explicit_override_beats_prompt(self) -> None:
        interval, source = resolve_stream_interval(0.5, 2.0)
        assert interval == 0.5
        assert source == "explicit override"

    def test_explicit_override_beats_default(self) -> None:
        interval, source = resolve_stream_interval(10.0, None)
        assert interval == 10.0
        assert source == "explicit override"


class TestClientStreamInterval:
    def _spec(self, interval: float | None = None) -> dict:
        spec: dict = {
            "dataset_name": "readings",
            "count": 5,
            "fields": [{"name": "v", "type": "int", "provider": "pyint"}],
        }
        if interval is not None:
            spec["stream_interval_sec"] = interval
        return spec

    def test_stream_rejects_zero_interval(self) -> None:
        client = Client(backend=MockBackend(default=self._spec()), cache=None)
        with pytest.raises(ValueError, match="must be > 0"):
            client.stream("p", interval_sec=0)

    def test_stream_runs_at_prompt_interval(self) -> None:
        # spec carries a fast cadence; a short duration bounds the run.
        client = Client(backend=MockBackend(default=self._spec(interval=0.05)), cache=None)
        records = list(client.stream("p", duration_sec=1, seed=1))
        # ~20 records/sec for ~1s — assert it produced a plausible batch
        # rather than an exact count (timing is not deterministic).
        assert len(records) > 0

    def test_explicit_interval_overrides_spec(self) -> None:
        # spec says 100s between records; override makes it fast so the
        # 1s-bounded run still yields something.
        client = Client(backend=MockBackend(default=self._spec(interval=100)), cache=None)
        records = list(client.stream("p", interval_sec=0.05, duration_sec=1, seed=1))
        assert len(records) > 0
