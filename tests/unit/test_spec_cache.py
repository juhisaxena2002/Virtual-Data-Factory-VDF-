"""Tests for the semantic spec cache.

These tests inject a deterministic ``embed_fn`` so we never need to
download MiniLM or load torch in CI. Chroma itself runs against a
``tmp_path`` SQLite store, so the user cache dir is never touched.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

# chromadb is the real store; without it the cache silently degrades to
# "always-miss" and these tests can't make meaningful assertions. Skip
# the whole module rather than producing false negatives.
pytest.importorskip("chromadb")

from synthgen import Client, SpecCache, Spec  # noqa: E402
from synthgen.backends import MockBackend  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _one_hot_embed(text: str, dims: int = 32) -> list[float]:
    """Deterministic embed: hash → single hot index in a small vector.

    Identical prompts → identical vectors (cosine similarity 1.0 → hit).
    Different prompts → almost-always different indexes (similarity 0.0 → miss).
    Good enough to exercise the cache's control flow without a real model.
    """
    h = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
    vec = [0.0] * dims
    vec[h % dims] = 1.0
    return vec


@pytest.fixture
def spec_dict() -> dict:
    return {
        "dataset_name": "users",
        "count": 10,
        "fields": [
            {"name": "user_id", "type": "uuid", "provider": "uuid4"},
            {"name": "email", "type": "string", "provider": "email"},
        ],
    }


@pytest.fixture
def cache(tmp_path: Path) -> SpecCache:
    return SpecCache(persist_dir=tmp_path, embed_fn=_one_hot_embed)


# ---------------------------------------------------------------------------
# SpecCache direct tests
# ---------------------------------------------------------------------------
class TestSpecCacheRoundTrip:
    def test_empty_cache_is_miss(self, cache: SpecCache) -> None:
        assert cache.get("anything") is None

    def test_put_then_get_same_prompt_hits(
        self, cache: SpecCache, spec_dict: dict
    ) -> None:
        spec = Spec.from_dict(spec_dict)
        cache.put("100 fake users", spec)
        hit = cache.get("100 fake users")
        assert hit is not None
        assert hit == spec

    def test_different_prompt_misses(
        self, cache: SpecCache, spec_dict: dict
    ) -> None:
        cache.put("100 fake users", Spec.from_dict(spec_dict))
        # Completely unrelated prompt — one-hot vector lands elsewhere.
        assert cache.get("temperature sensor readings") is None

    def test_put_overwrites_same_prompt(
        self, cache: SpecCache, spec_dict: dict
    ) -> None:
        cache.put("p", Spec.from_dict(spec_dict))
        updated = {**spec_dict, "dataset_name": "renamed"}
        cache.put("p", Spec.from_dict(updated))
        hit = cache.get("p")
        assert hit is not None
        assert hit.dataset_name == "renamed"

    def test_clear_wipes_entries(
        self, cache: SpecCache, spec_dict: dict
    ) -> None:
        cache.put("p", Spec.from_dict(spec_dict))
        assert cache.get("p") is not None
        cache.clear()
        assert cache.get("p") is None


class TestSpecCacheThreshold:
    def test_below_threshold_is_miss(
        self, tmp_path: Path, spec_dict: dict
    ) -> None:
        # Threshold of 1.01 → nothing ever counts as a hit.
        c = SpecCache(persist_dir=tmp_path, embed_fn=_one_hot_embed, threshold=1.01)
        c.put("p", Spec.from_dict(spec_dict))
        assert c.get("p") is None


class TestStaleSpecRejection:
    def test_invalid_cached_spec_yields_miss(
        self, cache: SpecCache
    ) -> None:
        # Bypass put() so we can store a spec dict that no longer validates.
        # An unknown provider should be rejected on re-validation → miss.
        import json
        bad_spec = {
            "dataset_name": "x",
            "count": 5,
            "fields": [{"name": "f", "type": "string", "provider": "nope_not_real"}],
        }
        cache._collection.upsert(
            ids=["fake-id"],
            embeddings=[_one_hot_embed("p")],
            documents=["p"],
            metadatas=[{"spec_json": json.dumps(bad_spec)}],
        )
        assert cache.get("p") is None


# ---------------------------------------------------------------------------
# Client integration
# ---------------------------------------------------------------------------
class TestClientCacheIntegration:
    def test_cache_none_calls_backend_every_time(self, spec_dict: dict) -> None:
        backend = MockBackend(default=spec_dict)
        client = Client(backend=backend, cache=None)
        client.compile_spec("a prompt")
        client.compile_spec("a prompt")
        assert len(backend.calls) == 2

    def test_cache_hit_skips_backend(
        self, tmp_path: Path, spec_dict: dict
    ) -> None:
        backend = MockBackend(default=spec_dict)
        cache = SpecCache(persist_dir=tmp_path, embed_fn=_one_hot_embed)
        client = Client(backend=backend, cache=cache)

        client.compile_spec("a prompt")
        client.compile_spec("a prompt")  # second call: should hit cache
        assert len(backend.calls) == 1

    def test_use_cache_false_forces_backend_call(
        self, tmp_path: Path, spec_dict: dict
    ) -> None:
        backend = MockBackend(default=spec_dict)
        cache = SpecCache(persist_dir=tmp_path, embed_fn=_one_hot_embed)
        client = Client(backend=backend, cache=cache)

        client.compile_spec("p")
        client.compile_spec("p", use_cache=False)  # bypass: another backend call
        assert len(backend.calls) == 2

    def test_different_prompts_each_call_backend(
        self, tmp_path: Path, spec_dict: dict
    ) -> None:
        backend = MockBackend(default=spec_dict)
        cache = SpecCache(persist_dir=tmp_path, embed_fn=_one_hot_embed)
        client = Client(backend=backend, cache=cache)

        client.compile_spec("alpha prompt")
        client.compile_spec("beta prompt")
        assert len(backend.calls) == 2


class TestStatsCounters:
    def test_hit_increments_hits(
        self, tmp_path: Path, spec_dict: dict
    ) -> None:
        cache = SpecCache(persist_dir=tmp_path, embed_fn=_one_hot_embed)
        cache.put("p", Spec.from_dict(spec_dict))
        cache.get("p")
        cache.get("p")
        assert cache.hits == 2
        assert cache.misses == 0

    def test_miss_increments_misses(self, cache: SpecCache) -> None:
        cache.get("never-stored")
        assert cache.hits == 0
        assert cache.misses == 1

    def test_reset_stats(
        self, cache: SpecCache, spec_dict: dict
    ) -> None:
        cache.put("p", Spec.from_dict(spec_dict))
        cache.get("p")
        cache.get("other")
        assert (cache.hits, cache.misses) == (1, 1)
        cache.reset_stats()
        assert (cache.hits, cache.misses, cache.errors) == (0, 0, 0)

    def test_last_similarity_set_on_hit(
        self, cache: SpecCache, spec_dict: dict
    ) -> None:
        cache.put("p", Spec.from_dict(spec_dict))
        cache.get("p")
        # Identical prompt → identical one-hot vector → cosine similarity 1.0.
        assert cache.last_similarity is not None
        assert cache.last_similarity == pytest.approx(1.0)

    def test_last_similarity_none_on_empty(self, cache: SpecCache) -> None:
        cache.get("never-stored")
        assert cache.last_similarity is None
