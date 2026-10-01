"""Build / update the index. Used by ingest.py and the UI's "Update index" button."""
from __future__ import annotations

import multiprocessing as mp
import os
import time
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from tqdm import tqdm

from . import extract, local
from .chunk import chunk_text
from .config import Settings
from .store import FileRecord, Store

FLUSH_CHUNKS = 512  # embed + commit after this many pending chunks
Log = Callable[[str], None]


class IngestError(RuntimeError):
    pass


@dataclass
class Summary:
    files: int = 0
    chunks: int = 0
    added_chunks: int = 0
    changed_files: int = 0
    removed_files: int = 0
    empty: int = 0
    failed: list[tuple[str, str]] = field(default_factory=list)
    seconds: float = 0.0
    interrupted: bool = False

    def text(self) -> str:
        lines = [
            f"{self.files} files / {self.chunks} passages searchable "
            f"({self.changed_files} new or changed, {self.removed_files} removed) in {self.seconds:.0f}s."
        ]
        if self.interrupted:
            lines.append("Stopped early: run it again to finish (finished files are kept).")
        if self.empty:
            lines.append(f"{self.empty} files had no extractable text (scanned without OCR, images, empty).")
        if self.failed:
            lines.append(f"{len(self.failed)} files could not be read:")
            lines += [f"  - {p}: {e[:150]}" for p, e in self.failed[:15]]
            if len(self.failed) > 15:
                lines.append(f"  ... and {len(self.failed) - 15} more")
        return "\n".join(lines)


def embed_text(path: str, location: str, chunk: str) -> str:
    """Text actually embedded: the folder path carries useful meaning (course, topic, ...)."""
    title = " / ".join(PurePosixPath(path).with_suffix("").parts)
    return f"{title} ({location})\n{chunk}" if location else f"{title}\n{chunk}"


class IngestLock:
    """Stop two ingests (e.g. terminal + UI) from writing the same index at once."""

    def __init__(self, index_dir: Path):
        self.path = Path(index_dir) / "ingest.lock"

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                return self
            except FileExistsError:
                if not self._stale():
                    raise IngestError("Another indexing run is already in progress.") from None
                self.path.unlink(missing_ok=True)
        raise IngestError(f"Could not create {self.path}")

    def _stale(self) -> bool:
        try:
            pid = int(self.path.read_text() or 0)
        except (OSError, ValueError):
            return True
        return not _pid_alive(pid) or time.time() - self.path.stat().st_mtime > 12 * 3600

    def __exit__(self, *exc):
        self.path.unlink(missing_ok=True)


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


class _Batcher:
    """Collects extracted files, embeds them in batches and writes them to the store."""

    def __init__(self, cfg: Settings, store: Store, summary: Summary, embedder, log: Log):
        self.cfg, self.store, self.summary, self.log = cfg, store, summary, log
        self.embedder = embedder
        self.pending: list[tuple[FileRecord, list[tuple[str, str]]]] = []
        self.n_pending = 0

    def _embedder(self):
        if self.embedder is None:
            from .embed import Embedder

            self.log(f"Loading embedding model {self.cfg.embed_model} ...")
            self.embedder = Embedder(self.cfg.embed_model)
        return self.embedder

    def add(self, rec: FileRecord, segments: list[tuple[str, str]], error: str) -> None:
        chunks = [
            (loc, c)
            for loc, text in segments
            for c in chunk_text(text, self.cfg.chunk_size, self.cfg.chunk_overlap)
        ]
        if error:
            rec.status, rec.error = "error", error
            self.summary.failed.append((rec.path, error))
        elif not chunks:
            rec.status = "empty"
            self.summary.empty += 1
        self.pending.append((rec, chunks))
        self.n_pending += len(chunks)
        if self.n_pending >= FLUSH_CHUNKS:
            self.flush()

    def flush(self) -> None:
        if not self.pending:
            return
        texts = [embed_text(r.path, loc, c) for r, chunks in self.pending for loc, c in chunks]
        vectors = self._embedder().encode(texts) if texts else None
        offset = 0
        for rec, chunks in self.pending:
            vecs = vectors[offset:offset + len(chunks)] if chunks else None
            offset += len(chunks)
            self.store.add_file(rec, chunks, vecs)
        self.store.commit()
        self.summary.added_chunks += len(texts)
        self.pending, self.n_pending = [], 0


def _sync(store: Store, source: str, current: list[FileRecord], summary: Summary, log: Log) -> list[FileRecord]:
    """Remove deleted/changed files from the index; return files that need (re)indexing."""
    known = store.file_versions(source)
    now = {r.path: r for r in current}
    stale = [p for p, v in known.items() if p not in now or now[p].version != v]
    store.delete_files(source, stale)
    todo = [r for r in current if known.get(r.path) != r.version]
    removed = sum(1 for p in known if p not in now)
    summary.changed_files += len(todo)
    summary.removed_files += removed
    log(f"  {len(current)} files found | {len(todo)} new/changed | {removed} removed")
    return todo


def _progress(total: int, desc: str, show: bool):
    return tqdm(total=total, desc=desc, unit="file", disable=not show)


def _local(cfg, store, batch, ocr, summary, log, show_progress) -> None:
    if not cfg.data_dir.is_dir():
        raise IngestError(
            f"Data folder not found: {cfg.data_dir}\n"
            "Create it and put your files inside, or set DOCTRACE_DATA_DIR in .env."
        )
    previous_root = store.get_meta("local_root")
    if previous_root and previous_root != str(cfg.data_dir):
        log(f"Data folder changed ({previous_root} -> {cfg.data_dir}); dropping old local entries.")
        store.delete_files("local", list(store.file_versions("local")))
    store.set_meta("local_root", str(cfg.data_dir))

    log(f"Scanning {cfg.data_dir} ...")
    records, skipped = local.scan(cfg.data_dir, cfg.index_dir, cfg.max_file_mb)
    if skipped:
        log("  skipped unsupported: " + ", ".join(f"{e} x{n}" for e, n in skipped.most_common(8)))
    todo = _sync(store, "local", records, summary, log)
    if not todo:
        return

    count = [0]
    with _progress(len(todo), "Indexing", show_progress) as bar:
        def done(rec, segments, error):
            batch.add(rec, segments, error)
            bar.update()
            count[0] += 1
            if not show_progress and (count[0] % 50 == 0 or count[0] == len(todo)):
                log(f"  processed {count[0]}/{len(todo)} files")

        crashed = _extract_parallel(todo, cfg, ocr, done)
        if crashed:
            # a file crashed a parser process; re-run those files one per process to find it
            log(f"  a parser crashed; retrying {len(crashed)} files in isolation ...")
            for rec in crashed:
                if _extract_parallel([rec], cfg, ocr, done):
                    done(rec, [], "the file crashed the parser (corrupt or unsupported)")


def _extract_parallel(records, cfg, ocr, done) -> list[FileRecord]:
    """Extract files in worker processes. Returns the files lost to a crashed worker."""
    # "spawn" is safe on every OS, and with torch already loaded in the parent
    pool = ProcessPoolExecutor(
        max_workers=min(cfg.workers, len(records)), mp_context=mp.get_context("spawn"),
        initializer=extract.init_worker, initargs=(ocr, cfg.tesseract_cmd),
    )
    crashed = []
    try:
        futures = {pool.submit(extract.extract_file, r.uri): r for r in records}
        for fut in as_completed(futures):
            try:
                segments, error = fut.result()
            except BrokenProcessPool:
                crashed.append(futures[fut])
                continue
            done(futures[fut], segments, error)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return crashed


def _gdrive(cfg, store, batch, ocr, summary, log, show_progress) -> None:
    from .gdrive import Drive

    if not cfg.gdrive_folder_id:
        raise IngestError("Google Drive indexing needs GDRIVE_FOLDER_ID in .env")
    drive = Drive(cfg.gdrive_credentials)
    log("Listing Google Drive files ...")
    files = drive.scan(cfg.gdrive_folder_id, cfg.max_file_mb)
    todo = {r.path for r in _sync(store, "gdrive", [f.record for f in files], summary, log)}
    files = [f for f in files if f.record.path in todo]
    if not files:
        return

    def work(f):
        try:
            return extract.extract(drive.download(f), f.ext, ocr=ocr), ""
        except Exception as e:  # noqa: BLE001
            return [], f"{type(e).__name__}: {e}"

    pool = ThreadPoolExecutor(max_workers=6)
    try:
        futures = {pool.submit(work, f): f for f in files}
        with _progress(len(futures), "Drive", show_progress) as bar:
            for fut in as_completed(futures):
                segments, error = fut.result()
                batch.add(futures[fut].record, segments, error)
                bar.update()
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def run_ingest(
    cfg: Settings,
    *,
    rebuild: bool = False,
    local_source: bool = True,
    gdrive: bool = False,
    embedder=None,
    log: Log = print,
    show_progress: bool = True,
) -> Summary:
    """Incrementally index the configured sources. Safe to interrupt with Ctrl+C."""
    start = time.time()
    summary = Summary()
    with IngestLock(cfg.index_dir):
        store = Store(cfg.index_dir)
        try:
            old_model = store.get_meta("embed_model")
            if rebuild or (old_model and old_model != cfg.embed_model):
                if not rebuild:
                    log(f"Embedding model changed ({old_model} -> {cfg.embed_model}); rebuilding.")
                store.reset()
            store.set_meta("embed_model", cfg.embed_model)
            if embedder is not None and embedder.name != cfg.embed_model:
                embedder = None

            ocr = extract.configure_ocr(cfg.ocr, cfg.tesseract_cmd)
            log("OCR for images / scanned PDFs: " + (
                "on" if ocr else "off" if cfg.ocr == "off" else "off (Tesseract not installed)"))

            batch = _Batcher(cfg, store, summary, embedder, log)
            try:
                if local_source:
                    _local(cfg, store, batch, ocr, summary, log, show_progress)
                if gdrive:
                    _gdrive(cfg, store, batch, ocr, summary, log, show_progress)
            except KeyboardInterrupt:
                summary.interrupted = True
                log("\nInterrupted - saving the files finished so far ...")
            # files that never finished are not in the index yet, so the next run retries them
            batch.flush()

            log("Building vector index ...")
            summary.chunks = store.build_faiss()
            summary.files = store.stats()["files"]
            store.set_meta("last_ingest", str(time.time()))
        finally:
            store.close()
    summary.seconds = time.time() - start
    return summary
