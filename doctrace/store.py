"""Persistent index: SQLite for files/chunks/keyword search, FAISS for vectors.

Layout of <index_dir>:
    doctrace.sqlite   - files, chunks (text + embedding), FTS5 keyword index, metadata
    index.faiss  - vector index rebuilt from the chunk embeddings after each ingest
"""
from __future__ import annotations

import re
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

SCHEMA_VERSION = "2"


@dataclass
class FileRecord:
    source: str   # "local" | "gdrive"
    path: str     # path relative to the source root, "/"-separated
    version: str  # changes whenever the file changes (mtime+size, Drive md5, ...)
    uri: str      # absolute local path or web link
    status: str = "ok"
    error: str = ""


@dataclass
class Chunk:
    id: int
    source: str
    path: str
    uri: str
    location: str
    text: str


_WORD = re.compile(r"\w+", re.UNICODE)
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for",
    "from", "how", "i", "in", "is", "it", "me", "my", "of", "on", "or", "the",
    "to", "was", "what", "when", "where", "which", "who", "why", "with", "you",
    "about", "give", "tell", "find", "show", "explain", "notes",
}


def fts_query(text: str) -> str:
    """Turn free text into a safe FTS5 OR-query of quoted terms."""
    terms = [w for w in _WORD.findall(text.lower()) if w not in _STOPWORDS and len(w) > 1]
    return " OR ".join(f'"{t}"' for t in dict.fromkeys(terms))


class Store:
    def __init__(self, index_dir: Path):
        self.dir = Path(index_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.dir / "doctrace.sqlite"
        self.faiss_path = self.dir / "index.faiss"
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._create()

    # ------------------------------------------------------------ schema
    def _create(self) -> None:
        c = self.conn
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY,
                source TEXT NOT NULL,
                path TEXT NOT NULL,
                version TEXT NOT NULL,
                uri TEXT NOT NULL,
                status TEXT NOT NULL,
                error TEXT,
                n_chunks INTEGER NOT NULL DEFAULT 0,
                indexed_at REAL NOT NULL,
                UNIQUE (source, path)
            );
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY,
                file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
                location TEXT,
                text TEXT NOT NULL,
                embedding BLOB NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_chunks_file ON chunks(file_id);
            """
        )
        try:
            c.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5("
                "title, text, tokenize='unicode61 remove_diacritics 2')"
            )
            self.has_fts = True
        except sqlite3.OperationalError:  # SQLite built without FTS5
            self.has_fts = False
        c.commit()
        if self.get_meta("schema") is None:
            self.set_meta("schema", SCHEMA_VERSION)

    def reset(self) -> None:
        with self._lock:
            self.conn.executescript(
                "DELETE FROM chunks; DELETE FROM files; DELETE FROM meta;"
                + ("DELETE FROM chunks_fts;" if self.has_fts else "")
            )
            self.conn.commit()
        self.set_meta("schema", SCHEMA_VERSION)
        self.faiss_path.unlink(missing_ok=True)

    # ------------------------------------------------------------ meta
    def get_meta(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def set_meta(self, key: str, value: str) -> None:
        with self._lock:
            self.conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, value))
            self.conn.commit()

    # ------------------------------------------------------------ writing
    def file_versions(self, source: str) -> dict[str, str]:
        rows = self.conn.execute("SELECT path, version FROM files WHERE source=?", (source,))
        return dict(rows.fetchall())

    def delete_files(self, source: str, paths: list[str]) -> None:
        with self._lock:
            for path in paths:
                row = self.conn.execute(
                    "SELECT id FROM files WHERE source=? AND path=?", (source, path)
                ).fetchone()
                if not row:
                    continue
                if self.has_fts:
                    self.conn.execute(
                        "DELETE FROM chunks_fts WHERE rowid IN "
                        "(SELECT id FROM chunks WHERE file_id=?)", (row[0],)
                    )
                self.conn.execute("DELETE FROM files WHERE id=?", (row[0],))
            self.conn.commit()

    def add_file(self, rec: FileRecord, chunks: list[tuple[str, str]], vectors: np.ndarray | None) -> None:
        """Insert one file and its (location, text) chunks. Caller commits."""
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO files (source, path, version, uri, status, error, n_chunks, indexed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (rec.source, rec.path, rec.version, rec.uri, rec.status, rec.error,
                 len(chunks), time.time()),
            )
            file_id = cur.lastrowid
            for (loc, text), vec in zip(chunks, vectors if vectors is not None else [], strict=True):
                cid = self.conn.execute(
                    "INSERT INTO chunks (file_id, location, text, embedding) VALUES (?, ?, ?, ?)",
                    (file_id, loc, text, vec.astype("float32").tobytes()),
                ).lastrowid
                if self.has_fts:
                    self.conn.execute(
                        "INSERT INTO chunks_fts (rowid, title, text) VALUES (?, ?, ?)",
                        (cid, rec.path.replace("/", " "), text),
                    )

    def close(self) -> None:
        with self._lock:
            self.conn.close()

    def commit(self) -> None:
        with self._lock:
            self.conn.commit()

    # ------------------------------------------------------------ vectors
    def load_embeddings(self, chunk_ids: list[int] | None = None) -> tuple[np.ndarray, np.ndarray]:
        """Return (ids, matrix) for all chunks, or only the given chunk ids."""
        if chunk_ids is None:
            rows = self.conn.execute("SELECT id, embedding FROM chunks ORDER BY id").fetchall()
        else:
            rows = []
            for i in range(0, len(chunk_ids), 900):
                part = chunk_ids[i:i + 900]
                q = f"SELECT id, embedding FROM chunks WHERE id IN ({','.join('?' * len(part))})"
                rows += self.conn.execute(q, part).fetchall()
        if not rows:
            return np.empty(0, dtype="int64"), np.empty((0, 0), dtype="float32")
        ids = np.fromiter((r[0] for r in rows), dtype="int64", count=len(rows))
        mat = np.vstack([np.frombuffer(r[1], dtype="float32") for r in rows])
        return ids, mat

    def build_faiss(self) -> int:
        import faiss

        ids, mat = self.load_embeddings()
        if len(ids) == 0:
            self.faiss_path.unlink(missing_ok=True)
            return 0
        index = faiss.IndexIDMap2(faiss.IndexFlatIP(mat.shape[1]))
        index.add_with_ids(mat, ids)
        # serialize via numpy so non-ASCII paths work on Windows
        tmp = self.faiss_path.with_suffix(".tmp")
        faiss.serialize_index(index).tofile(tmp)
        tmp.replace(self.faiss_path)
        return index.ntotal

    def load_faiss(self):
        import faiss

        if not self.faiss_path.exists():
            return None
        return faiss.deserialize_index(np.fromfile(self.faiss_path, dtype="uint8"))

    # ------------------------------------------------------------ reading
    def chunks_by_id(self, ids: list[int]) -> dict[int, Chunk]:
        out: dict[int, Chunk] = {}
        for i in range(0, len(ids), 900):
            part = ids[i:i + 900]
            q = (
                "SELECT c.id, f.source, f.path, f.uri, c.location, c.text FROM chunks c "
                f"JOIN files f ON f.id = c.file_id WHERE c.id IN ({','.join('?' * len(part))})"
            )
            for row in self.conn.execute(q, part):
                out[row[0]] = Chunk(*row)
        return out

    def chunk_ids_under(self, folder: str) -> list[int]:
        rows = self.conn.execute(
            "SELECT c.id FROM chunks c JOIN files f ON f.id = c.file_id "
            "WHERE f.path = ? OR f.path LIKE ? ESCAPE '\\'",
            (folder, _like_prefix(folder)),
        )
        return [r[0] for r in rows]

    def keyword_search(self, query: str, limit: int, folder: str = "") -> list[int]:
        if not self.has_fts:
            return []
        match = fts_query(query)
        if not match:
            return []
        sql = "SELECT fts.rowid FROM chunks_fts fts "
        params: list = [match]
        if folder:
            sql += "JOIN chunks c ON c.id = fts.rowid JOIN files f ON f.id = c.file_id "
        sql += "WHERE chunks_fts MATCH ? "
        if folder:
            sql += "AND (f.path = ? OR f.path LIKE ? ESCAPE '\\') "
            params += [folder, _like_prefix(folder)]
        sql += "ORDER BY rank LIMIT ?"
        params.append(limit)
        try:
            return [r[0] for r in self.conn.execute(sql, params)]
        except sqlite3.OperationalError:
            return []

    def folders(self, max_depth: int = 3) -> list[str]:
        seen: set[str] = set()
        for (path,) in self.conn.execute("SELECT path FROM files WHERE n_chunks > 0"):
            parts = path.split("/")[:-1]
            for d in range(1, min(len(parts), max_depth) + 1):
                seen.add("/".join(parts[:d]))
        return sorted(seen, key=str.lower)

    def is_local_file(self, uri: str) -> bool:
        row = self.conn.execute("SELECT 1 FROM files WHERE source='local' AND uri=?", (uri,)).fetchone()
        return row is not None

    def problem_files(self, limit: int = 200) -> list[tuple[str, str, str]]:
        """(path, status, error) for files that produced no searchable text."""
        return self.conn.execute(
            "SELECT path, status, COALESCE(error, '') FROM files WHERE n_chunks = 0 "
            "ORDER BY status, path LIMIT ?", (limit,)
        ).fetchall()

    def stats(self) -> dict[str, int]:
        q = self.conn.execute
        return {
            "files": q("SELECT COUNT(*) FROM files WHERE n_chunks > 0").fetchone()[0],
            "chunks": q("SELECT COUNT(*) FROM chunks").fetchone()[0],
            "skipped": q("SELECT COUNT(*) FROM files WHERE n_chunks = 0").fetchone()[0],
        }


def _like_prefix(folder: str) -> str:
    escaped = folder.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return escaped.rstrip("/") + "/%"
