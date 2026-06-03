"""Semantic prompt → Spec cache.

Wraps a vector store (Chroma persistent) and an embedder
(sentence-transformers MiniLM by default). Before a backend.compile_spec()
call, the Client can ask the cache for a previously-compiled Spec whose
prompt is semantically similar to the current prompt — on a hit, the
LLM call is skipped.

Defaults:

* Embedder: ``sentence-transformers/all-MiniLM-L6-v2`` (CPU, ~80MB).
* Store:    ``chromadb.PersistentClient`` under platformdirs' user cache.
* Threshold: cosine similarity ≥ 0.92 counts as a hit.

The embedder and the Chroma collection are both constructed lazily on
first use so that importing this module stays cheap.
"""

from __future__ import annotations

import hashlib
import json
import logging
import warnings
from functools import cached_property
from pathlib import Path
from typing import Any, Callable

import numpy as np

from . import _schema
from .types import Spec

_logger = logging.getLogger(__name__)


def _cosine_similarity(a: Any, b: Any) -> float:
    """Cosine similarity of two vectors, in [-1, 1].

    Computed directly from the embeddings rather than read off Chroma's
    distance metric — the metric a collection uses varies by Chroma
    version and config, so ``1 - distance`` is not portable. This is.
    """
    va = np.asarray(a, dtype=float).ravel()
    vb = np.asarray(b, dtype=float).ravel()
    na = float(np.linalg.norm(va))
    nb = float(np.linalg.norm(vb))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))

# Bump when the cached Spec representation changes in a backwards-incompatible
# way so old entries become inaccessible rather than silently mis-deserialised.
_COLLECTION_NAME = "synthgen_specs_v1"

_DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
# 0.85 separates "same dataset, reworded" (MiniLM ~0.90+) from genuinely
# different requests (~0.70 and below). 0.92 was too strict — it missed
# even same-spec prompts that differed only in row count.
_DEFAULT_THRESHOLD = 0.85


def _default_persist_dir() -> Path:
    try:
        from platformdirs import user_cache_dir
        return Path(user_cache_dir("synthgen")) / "spec_cache"
    except ImportError:
        return Path.home() / ".cache" / "synthgen" / "spec_cache"


class SpecCache:
    """Semantic prompt → Spec cache.

    Parameters
    ----------
    persist_dir
        Directory for Chroma's SQLite store. Defaults to a
        platform-appropriate user cache dir.
    model_name
        sentence-transformers model id. Ignored when ``embed_fn`` is set.
    threshold
        Cosine similarity threshold (0–1) above which a neighbour counts
        as a hit. Default 0.85 — raise it to be stricter, lower it for
        more cache hits at the risk of looser matches.
    embed_fn
        Optional callable ``str -> list[float]``. Lets tests inject a
        deterministic fake without loading torch.

    Attributes
    ----------
    hits, misses, errors
        Running counters for the lifetime of the instance — handy for
        verifying that the cache is actually being used. ``hits`` counts
        returned cached specs; ``misses`` counts every other path
        (empty collection, below-threshold neighbour, stale spec);
        ``errors`` counts caught exceptions during get/put. Reset with
        :meth:`reset_stats`.
    last_similarity
        Cosine similarity (0–1) of the nearest neighbour found by the
        most recent :meth:`get` call, or ``None`` when the collection
        was empty or the lookup errored. Lets callers report the match
        percentage even though :meth:`get` only returns the spec.
    """

    def __init__(
        self,
        persist_dir: Path | str | None = None,
        *,
        model_name: str = _DEFAULT_MODEL,
        threshold: float = _DEFAULT_THRESHOLD,
        embed_fn: Callable[[str], list[float]] | None = None,
    ) -> None:
        self._persist_dir = (
            Path(persist_dir) if persist_dir is not None else _default_persist_dir()
        )
        self._model_name = model_name
        self._threshold = float(threshold)
        self._embed_fn = embed_fn
        self.hits = 0
        self.misses = 0
        self.errors = 0
        self.last_similarity: float | None = None

    # ------------------------------------------------------------------
    # Lazy resources — first-touch cost is paid here, not at __init__
    # ------------------------------------------------------------------
    @cached_property
    def _model(self) -> Any:
        from sentence_transformers import SentenceTransformer
        # Offline-first: load from the local HF cache with no network
        # calls. Only the very first run (model not yet downloaded)
        # falls back to an online load that fetches it once.
        try:
            return SentenceTransformer(self._model_name, local_files_only=True)
        except Exception:
            _logger.info(
                "embedding model %r not cached - downloading once (~80MB)",
                self._model_name,
            )
            return SentenceTransformer(self._model_name)

    @cached_property
    def _collection(self) -> Any:
        import chromadb
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(self._persist_dir))
        # Force cosine space — Chroma's default is L2.
        return client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # Embedding
    # ------------------------------------------------------------------
    def _embed(self, text: str) -> list[float]:
        if self._embed_fn is not None:
            return self._embed_fn(text)
        vec = self._model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [float(x) for x in vec.tolist()]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get(self, prompt: str) -> Spec | None:
        """Return a cached Spec whose source prompt is semantically similar.

        Returns ``None`` when:

        * The collection is empty.
        * The nearest neighbour's cosine similarity is below ``threshold``.
        * The stored spec no longer passes validation (e.g. provider
          removed in a newer release) — re-validation guards against
          stale entries.

        Any internal failure (embed error, IO error) is swallowed with a
        warning so the caller can fall through to the LLM. Caching must
        never break correctness.
        """
        self.last_similarity = None
        try:
            embedding = self._embed(prompt)
            result = self._collection.query(
                query_embeddings=[embedding],
                n_results=1,
                include=["embeddings", "metadatas"],
            )
        except Exception as e:
            self.errors += 1
            warnings.warn(f"SpecCache.get failed, bypassing cache: {e}", stacklevel=2)
            return None

        # query() returns one result row per query embedding; we sent one.
        rows = result.get("embeddings")
        neighbours = rows[0] if rows is not None and len(rows) else None
        if neighbours is None or len(neighbours) == 0:
            self.misses += 1
            _logger.debug("SpecCache miss (empty collection) for %r", prompt[:80])
            return None

        # Score the neighbour ourselves with cosine similarity instead of
        # trusting Chroma's distance metric (see _cosine_similarity).
        similarity = _cosine_similarity(embedding, neighbours[0])
        self.last_similarity = similarity
        if similarity < self._threshold:
            self.misses += 1
            _logger.debug(
                "SpecCache miss (similarity %.3f < %.3f) for %r",
                similarity, self._threshold, prompt[:80],
            )
            return None

        meta_rows = result.get("metadatas")
        meta_row = meta_rows[0] if meta_rows is not None and len(meta_rows) else None
        metadata = meta_row[0] if meta_row is not None and len(meta_row) else {}
        raw = metadata.get("spec_json") if metadata else None
        if not raw:
            self.misses += 1
            return None
        try:
            spec = _schema.validate_spec(json.loads(raw))
        except Exception:
            self.misses += 1
            _logger.debug("SpecCache miss (stale spec rejected) for %r", prompt[:80])
            return None

        self.hits += 1
        _logger.debug(
            "SpecCache hit (similarity %.3f) for %r", similarity, prompt[:80],
        )
        return spec

    def put(self, prompt: str, spec: Spec) -> None:
        """Embed ``prompt`` and store the ``(embedding → spec)`` entry.

        Failures are swallowed with a warning — a cache write that
        crashes the user's generation call would be worse than missing
        the write.
        """
        try:
            embedding = self._embed(prompt)
            spec_json = json.dumps(spec.to_dict())
            # Deterministic id → re-puts of the same prompt overwrite
            # instead of accumulating duplicate rows.
            entry_id = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
            self._collection.upsert(
                ids=[entry_id],
                embeddings=[embedding],
                documents=[prompt],
                metadatas=[{"spec_json": spec_json}],
            )
        except Exception as e:
            self.errors += 1
            warnings.warn(f"SpecCache.put failed, entry not stored: {e}", stacklevel=2)

    def clear(self) -> None:
        """Delete every cached entry."""
        import chromadb
        client = chromadb.PersistentClient(path=str(self._persist_dir))
        try:
            client.delete_collection(_COLLECTION_NAME)
        except Exception:
            pass
        # Drop the cached handle so the next access rebuilds the collection.
        self.__dict__.pop("_collection", None)

    def reset_stats(self) -> None:
        """Zero out ``hits`` / ``misses`` / ``errors``."""
        self.hits = 0
        self.misses = 0
        self.errors = 0
