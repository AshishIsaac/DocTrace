import re
import sys
import zlib
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class FakeEmbedder:
    """Bag-of-words hashing embedder: deterministic, instant, no model download."""

    dim = 512

    def __init__(self, name: str):
        self.name = name

    def encode(self, texts, **_):
        out = np.zeros((len(texts), self.dim), dtype="float32")
        for i, text in enumerate(texts):
            for word in re.findall(r"\w+", text.lower()):
                out[i, zlib.crc32(word.encode()) % self.dim] += 1.0
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        return out / np.where(norms == 0, 1, norms)


@pytest.fixture(autouse=True)
def fake_embedder(monkeypatch):
    import doctrace.embed
    import doctrace.search

    monkeypatch.setattr(doctrace.embed, "Embedder", FakeEmbedder)
    monkeypatch.setattr(doctrace.search, "Embedder", FakeEmbedder)


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    from doctrace.config import load_settings

    for key in ("DOCTRACE_DATA_DIR", "DOCTRACE_LLM", "DOCTRACE_EMBED_MODEL", "DOCTRACE_CHUNK_SIZE"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("DOCTRACE_INDEX_DIR", str(tmp_path / "index"))
    monkeypatch.setenv("DOCTRACE_OCR", "off")
    monkeypatch.setenv("DOCTRACE_WORKERS", "2")
    data = tmp_path / "data"
    data.mkdir()
    return load_settings(str(data))
