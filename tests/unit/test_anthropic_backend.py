"""Tests for AnthropicBackend.

We mock the ``anthropic`` SDK so these tests run without a real API
key, network access, or token cost. Real-API tests live in the eval
harness, gated by ANTHROPIC_API_KEY presence.
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from synthgen import BackendError, BackendResponseError
from synthgen.backends import AnthropicBackend, Backend


def _make_message(blocks: list) -> SimpleNamespace:
    """Build a fake anthropic.types.Message with the given content blocks."""
    return SimpleNamespace(content=blocks, stop_reason="tool_use")


def _make_tool_use_block(name: str, input_dict: dict) -> SimpleNamespace:
    """Build a fake content block of type='tool_use'."""
    return SimpleNamespace(type="tool_use", name=name, input=input_dict)


class TestConstruction:
    def test_requires_api_key(self) -> None:
        # Ensure neither env var is set
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(BackendError, match="No Anthropic API key"):
                AnthropicBackend()

    def test_reads_api_key_from_env(self) -> None:
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            backend = AnthropicBackend()
            assert backend.name == "anthropic"

    def test_explicit_api_key_overrides_env(self) -> None:
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-key"}):
            backend = AnthropicBackend(api_key="explicit-key")
            # Cannot easily inspect the underlying client's key, but the
            # constructor should accept the override without complaint.
            assert backend.name == "anthropic"


class TestProtocolConformance:
    def test_conforms_to_backend_protocol(self) -> None:
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            backend = AnthropicBackend()
            assert isinstance(backend, Backend)

    def test_supports_tool_use(self) -> None:
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            assert AnthropicBackend().supports_tool_use() is True


class TestCompileSpec:
    """Happy and error paths for compile_spec, with the SDK fully mocked."""

    def _make_backend(self) -> AnthropicBackend:
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            return AnthropicBackend()

    def test_returns_tool_use_input(self) -> None:
        backend = self._make_backend()
        expected_spec = {"dataset_name": "users", "fields": [{"name": "x"}]}
        fake_response = _make_message([
            _make_tool_use_block("emit_spec", expected_spec)
        ])
        backend._client = MagicMock()
        backend._client.messages.create.return_value = fake_response

        result = backend.compile_spec(
            "generate users",
            system_prompt="you are a spec designer",
            tools=[{"name": "emit_spec", "input_schema": {}}],
        )
        assert result == expected_spec

    def test_passes_prompt_and_system_to_anthropic(self) -> None:
        backend = self._make_backend()
        fake_response = _make_message([
            _make_tool_use_block("emit_spec", {"dataset_name": "x", "fields": []})
        ])
        backend._client = MagicMock()
        backend._client.messages.create.return_value = fake_response

        backend.compile_spec(
            "user-prompt",
            system_prompt="system-prompt",
            tools=[{"name": "emit_spec"}],
        )
        call_kwargs = backend._client.messages.create.call_args.kwargs
        assert call_kwargs["system"] == "system-prompt"
        assert call_kwargs["messages"] == [{"role": "user", "content": "user-prompt"}]
        assert call_kwargs["tools"] == [{"name": "emit_spec"}]
        # Forced tool choice
        assert call_kwargs["tool_choice"] == {"type": "tool", "name": "emit_spec"}

    def test_skips_text_blocks_and_finds_tool_use(self) -> None:
        backend = self._make_backend()
        expected_spec = {"dataset_name": "x", "fields": []}
        text_block = SimpleNamespace(type="text", text="some prose")
        fake_response = _make_message([
            text_block,
            _make_tool_use_block("emit_spec", expected_spec),
        ])
        backend._client = MagicMock()
        backend._client.messages.create.return_value = fake_response

        assert backend.compile_spec("p", system_prompt="s", tools=[]) == expected_spec

    def test_missing_emit_spec_block_raises(self) -> None:
        backend = self._make_backend()
        # Response has only a text block — no tool_use.
        fake_response = _make_message([
            SimpleNamespace(type="text", text="I cannot do that")
        ])
        backend._client = MagicMock()
        backend._client.messages.create.return_value = fake_response

        with pytest.raises(BackendResponseError, match="emit_spec"):
            backend.compile_spec("p", system_prompt="s", tools=[])

    def test_api_failure_raises_backend_error(self) -> None:
        backend = self._make_backend()
        backend._client = MagicMock()
        backend._client.messages.create.side_effect = RuntimeError("network down")

        with pytest.raises(BackendError, match="failed"):
            backend.compile_spec("p", system_prompt="s", tools=[])
