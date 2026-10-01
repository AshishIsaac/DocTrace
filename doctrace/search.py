"""Hybrid retrieval: semantic (FAISS) + keyword (SQLite FTS5), fused with RRF."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field

import numpy as np

from .config import Settings
from .embed import Embedder
from .store import Chunk, Store

RRF_K = 60
# Vector-only matches below this cosine similarity are noise; keyword matches are always kept.
MIN_SIMILARITY = 0.2


@dataclass
class Hit:
    chunk: Chunk
    score: float                 # fused rank score (higher is better)
    similarity: float | None     # cosine similarity, if found by the vector search
    keyword: bool                # found by the keyword search


@dataclass
class FileResult:
    source: str
    path: str
    uri: str
    hits: list[Hit] = field(default_factory=list)

    @property
    def best(self) -> Hit:
        return self.hits[0]


class SearchEngine:
    def __init__(self, cfg: Settings, log=print):
        self.cfg = cfg
        self.log = log
        self.embedder: Embedder | None = None
        self.store: Store | None = None
        self.index = None
        self._lock = threading.RLock()
        self.reload()

    def reload(self) -> None:
        """(Re)open the index from disk, e.g. after an ingest run."""
        store = Store(self.cfg.index_dir)
        index = None
        if store.stats()["chunks"]:
            index = store.load_faiss()
            if index is None or index.ntotal != store.stats()["chunks"]:
                self.log("Vector index is missing or out of date; rebuilding it from the database ...")
                store.build_faiss()
                index = store.load_faiss()
        model = store.get_meta("embed_model") or self.cfg.embed_model
        if self.embedder is None or self.embedder.name != model:
            self.log(f"Loading embedding model {model} ...")
            self.embedder = Embedder(model)
        with self._lock:
            old, self.store, self.index = self.store, store, index
        if old is not None:
            old.close()

    @property
    def ready(self) -> bool:
        return self.index is not None and self.index.ntotal > 0

    # ------------------------------------------------------------ retrieval
    def _vector(self, qvec: np.ndarray, n: int, folder: str) -> list[tuple[int, float]]:
        if folder:
            # exact search restricted to the folder
            ids, mat = self.store.load_embeddings(self.store.chunk_ids_under(folder))
            if len(ids) == 0:
                return []
            sims = mat @ qvec[0]
            top = np.argsort(-sims)[:n]
            return [(int(ids[i]), float(sims[i])) for i in top]
        sims, ids = self.index.search(qvec, min(n, self.index.ntotal))
        return [(int(i), float(s)) for i, s in zip(ids[0], sims[0], strict=True) if i != -1]

    def search_chunks(self, query: str, n: int = 50, folder: str = "") -> list[Hit]:
        query = query.strip()
        if not query or not self.ready:
            return []
        with self._lock:
            return self._search_chunks(query, n, folder)

    def _search_chunks(self, query: str, n: int, folder: str) -> list[Hit]:
        qvec = self.embedder.encode([query])
        kw = self.store.keyword_search(query, n, folder)
        kw_set = set(kw)
        vec = [(cid, s) for cid, s in self._vector(qvec, n, folder)
               if s >= MIN_SIMILARITY or cid in kw_set]

        scores: dict[int, float] = {}
        for rank, (cid, _) in enumerate(vec):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + rank)
        for rank, cid in enumerate(kw):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + rank)

        sim = dict(vec)
        chunks = self.store.chunks_by_id(list(scores))
        hits = [
            Hit(chunks[cid], s, sim.get(cid), cid in kw_set)
            for cid, s in scores.items() if cid in chunks
        ]
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits

    def search(self, query: str, k: int = 8, folder: str = "", per_file: int = 3
               ) -> tuple[list[FileResult], list[Hit]]:
        """Return (top-k files with their best matching passages, top raw chunks)."""
        hits = self.search_chunks(query, max(50, k * 8), folder)
        files: dict[tuple[str, str], FileResult] = {}
        for h in hits:
            key = (h.chunk.source, h.chunk.path)
            if key not in files:
                if len(files) >= k:
                    continue
                files[key] = FileResult(h.chunk.source, h.chunk.path, h.chunk.uri)
            if len(files[key].hits) < per_file:
                files[key].hits.append(h)
        return list(files.values()), hits

    def folders(self) -> list[str]:
        with self._lock:
            return self.store.folders()
