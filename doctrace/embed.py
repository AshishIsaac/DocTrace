"""Sentence-transformer wrapper that returns L2-normalised float32 vectors."""
from __future__ import annotations

import threading

import numpy as np


def _quiet_transformers() -> None:
    """Hide the "Loading weights" progress bars and advisory warnings."""
    try:
        from transformers.utils import logging as hf_logging

        hf_logging.set_verbosity_error()
        hf_logging.disable_progress_bar()
    except Exception:  # noqa: BLE001
        pass


def load_model(model_name: str, local_only: bool = False):
    """Load a SentenceTransformer, preferring the cached copy (fast, works offline)."""
    from sentence_transformers import SentenceTransformer

    _quiet_transformers()
    try:
        return SentenceTransformer(model_name, local_files_only=True)
    except Exception:  # noqa: BLE001 - not cached yet
        if local_only:
            raise
        return SentenceTransformer(model_name)


class Embedder:
    def __init__(self, model_name: str):
        self.name = model_name
        self._lock = threading.Lock()  # shared by searches and background indexing
        self.model = load_model(model_name)
        get_dim = getattr(self.model, "get_embedding_dimension", None) or \
            self.model.get_sentence_embedding_dimension
        self.dim = int(get_dim())

    def encode(self, texts: list[str], batch_size: int = 64, progress: bool = False) -> np.ndarray:
        with self._lock:
            vecs = self.model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=progress,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
        return np.ascontiguousarray(vecs, dtype="float32")
