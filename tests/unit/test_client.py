"""Tests for synthgen.Client with MockBackend."""

from __future__ import annotations

import pytest

from synthgen import (
    BackendError,
    BackendResponseError,
    Client,
    SpecValidationError,
)
from synthgen.backends import MockBackend


class TestClientConstruction:
    def test_requires_backend(self) -> None:
        with pytest.raises(TypeError):
            Client(backend=None)  # type: ignore[arg-type]

    def test_backend_name_exposed(self, mock_client: Client) -> None:
        assert mock_client.backend_name == "mock"


class TestGenerate:
    def test_calls_backend_once(self, simple_spec_dict: dict) -> None:
        backend = MockBackend(default=simple_spec_dict)
        client = Client(backend=backend, cache=None)
        client.generate("anything", count=5)
        assert len(backend.calls) == 1

    def test_passes_prompt_to_backend(self, simple_spec_dict: dict) -> None:
        backend = MockBackend(default=simple_spec_dict)
        client = Client(backend=backend, cache=None)
        client.generate("my custom prompt", count=5)
        assert backend.calls[0]["prompt"] == "my custom prompt"

    def test_count_clamped_to_cap(self, simple_spec_dict: dict) -> None:
        backend = MockBackend(default=simple_spec_dict)
        client = Client(backend=backend, max_row_cap=20, cache=None)
        records = client.generate("prompt", count=500)
        assert len(records) == 20

    def test_seeded_runs_deterministic(self, simple_spec_dict: dict) -> None:
        backend = MockBackend(default=simple_spec_dict)
        client = Client(backend=backend, cache=None)
        a = client.generate("p", count=5, seed=42)
        b = client.generate("p", count=5, seed=42)
        assert a == b


class TestCompileSpec:
    def test_returns_typed_spec(self, mock_client: Client) -> None:
        spec = mock_client.compile_spec("any prompt")
        assert spec.dataset_name == "users"
        assert len(spec.fields) == 2

    def test_invalid_spec_raises_validation_error(self) -> None:
        # Mock returns a spec missing required fields.
        backend = MockBackend(default={"dataset_name": "x"})
        client = Client(backend=backend, cache=None)
        with pytest.raises(SpecValidationError):
            client.compile_spec("anything")


class TestGenerateFromSpec:
    def test_bypasses_backend(self, mock_client: Client, simple_spec_dict: dict) -> None:
        backend = MockBackend(default=simple_spec_dict)
        client = Client(backend=backend, cache=None)
        # Compile once via the LLM ...
        spec = client.compile_spec("first prompt")
        # ... then generate from the spec without further LLM calls.
        client.generate_from_spec(spec, count=3)
        client.generate_from_spec(spec, count=3)
        # Only the compile_spec call hit the backend.
        assert len(backend.calls) == 1


class TestBackendErrorPropagation:
    def test_backend_error_propagates(self) -> None:
        backend = MockBackend(
            raise_on={"bad-prompt": BackendError("simulated network failure")},
        )
        client = Client(backend=backend, cache=None)
        with pytest.raises(BackendError, match="simulated"):
            client.generate("bad-prompt")

    def test_response_error_propagates(self) -> None:
        # MockBackend with no default and no canned response raises by default.
        backend = MockBackend()
        client = Client(backend=backend, cache=None)
        with pytest.raises(BackendResponseError):
            client.generate("anything")
