"""Tests for the backend protocol and MockBackend."""

from __future__ import annotations

import pytest

from synthgen import BackendError, BackendResponseError
from synthgen.backends import Backend, MockBackend


class TestBackendProtocol:
    def test_mock_backend_conforms(self) -> None:
        backend = MockBackend()
        assert isinstance(backend, Backend)

    def test_protocol_requires_name(self) -> None:
        # If someone defines a backend without name, the runtime check
        # via isinstance(Backend) should still succeed (Protocol is
        # structural), but the absence of a name attr would break callers.
        assert MockBackend().name == "mock"


class TestMockBackend:
    def test_default_response(self) -> None:
        backend = MockBackend(default={"dataset_name": "x", "fields": []})
        out = backend.compile_spec("p", system_prompt="s", tools=[])
        assert out == {"dataset_name": "x", "fields": []}

    def test_canned_response_per_prompt(self) -> None:
        backend = MockBackend(
            responses={"hello": {"k": 1}, "world": {"k": 2}},
        )
        assert backend.compile_spec("hello", system_prompt="", tools=[]) == {"k": 1}
        assert backend.compile_spec("world", system_prompt="", tools=[]) == {"k": 2}

    def test_no_match_raises(self) -> None:
        backend = MockBackend()
        with pytest.raises(BackendResponseError):
            backend.compile_spec("anything", system_prompt="", tools=[])

    def test_can_raise_configured_exception(self) -> None:
        backend = MockBackend(
            raise_on={"boom": BackendError("simulated failure")},
        )
        with pytest.raises(BackendError, match="simulated failure"):
            backend.compile_spec("boom", system_prompt="", tools=[])

    def test_records_calls(self) -> None:
        backend = MockBackend(default={"dataset_name": "x", "fields": []})
        backend.compile_spec("p1", system_prompt="s1", tools=[{"t": 1}])
        backend.compile_spec("p2", system_prompt="s2", tools=[{"t": 2}])
        assert len(backend.calls) == 2
        assert backend.calls[0]["prompt"] == "p1"
        assert backend.calls[1]["prompt"] == "p2"

    def test_supports_tool_use(self) -> None:
        assert MockBackend().supports_tool_use() is True
