"""Walk a local folder tree and list the files worth indexing."""
from __future__ import annotations

import os
from collections import Counter
from pathlib import Path

from .config import ROOT
from .extract import SUPPORTED_EXTS
from .store import FileRecord

PLACEHOLDER = ROOT / "data" / "README.md"
SKIP_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "env", "__pycache__", "node_modules",
    ".ipynb_checkpoints", ".idea", ".vscode", "$RECYCLE.BIN", "System Volume Information",
}


def scan(data_dir: Path, index_dir: Path, max_file_mb: float) -> tuple[list[FileRecord], Counter]:
    """Return indexable files under data_dir and a Counter of skipped extensions."""
    data_dir = data_dir.resolve()
    # never index this project's own code or its index, even if data_dir contains them
    blocked = {index_dir.resolve(), ROOT / "doctrace"}
    if data_dir != ROOT:
        blocked.add(ROOT)
    max_bytes = max_file_mb * 1024 * 1024

    records: list[FileRecord] = []
    skipped: Counter = Counter()
    for dirpath, dirnames, filenames in os.walk(data_dir):
        here = Path(dirpath)
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in SKIP_DIRS and not d.startswith(".") and (here / d).resolve() not in blocked
        )
        for name in sorted(filenames):
            if name.startswith((".", "~$")):  # hidden files, Office lock files
                continue
            full = here / name
            ext = full.suffix.lower()
            if ext not in SUPPORTED_EXTS:
                skipped[ext or "(no extension)"] += 1
                continue
            if (data_dir == ROOT and here == ROOT) or full == PLACEHOLDER:
                continue  # this project's own README / requirements etc.
            try:
                st = full.stat()
            except OSError:
                continue
            if st.st_size == 0 or st.st_size > max_bytes:
                skipped["(empty or too large)"] += 1
                continue
            records.append(FileRecord(
                source="local",
                path=full.relative_to(data_dir).as_posix(),
                version=f"{st.st_mtime_ns}:{st.st_size}",
                uri=str(full),
            ))
    return records, skipped
