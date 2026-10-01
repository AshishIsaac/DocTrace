"""Start DocTrace: update the index only if your files changed, then open the app.

    python run.py                  # check the data folder, index if needed, open the web UI
    python run.py --no-browser     # any search_app.py option is passed through
    python run.py -q "deadlock"    # ... including a one-off terminal search

The check only compares file names, sizes and modification times with the index,
so it takes a second even for large folders. Works with or without activating
.venv: if the project's environment exists, it is used automatically.
"""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
VENV_PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
SHOW_FILES = 10


def _use_project_venv() -> None:
    """Re-run this script with .venv's Python when started from another interpreter."""
    if Path(sys.prefix).resolve() == VENV.resolve() or not VENV_PY.exists():
        return
    try:
        sys.exit(subprocess.call([str(VENV_PY), str(Path(__file__).resolve()), *sys.argv[1:]]))
    except KeyboardInterrupt:
        sys.exit(130)


@dataclass
class Changes:
    new: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    reason: str = ""      # set when the whole index must be rebuilt
    indexed: int = 0      # files currently in the index (local folder)

    @property
    def needed(self) -> bool:
        return bool(self.reason or self.new or self.changed or self.removed)


def find_changes(cfg) -> Changes:
    """Compare the data folder with the index without reading or indexing anything."""
    from doctrace import local
    from doctrace.store import Store

    store = Store(cfg.index_dir)
    try:
        known = store.file_versions("local")
        out = Changes(indexed=len(known))
        old_model = store.get_meta("embed_model")
        old_root = store.get_meta("local_root")
        if old_model and old_model != cfg.embed_model:
            out.reason = f"the search model changed ({old_model} -> {cfg.embed_model})"
        elif old_root and old_root != str(cfg.data_dir):
            out.reason = f"the data folder changed ({old_root} -> {cfg.data_dir})"

        records, _ = local.scan(cfg.data_dir, cfg.index_dir, cfg.max_file_mb)
        current = {r.path: r.version for r in records}
        out.new = sorted(p for p in current if p not in known)
        out.changed = sorted(p for p, v in current.items() if p in known and known[p] != v)
        out.removed = sorted(p for p in known if p not in current)
        return out
    finally:
        store.close()


def _list(symbol: str, label: str, paths: list[str]) -> None:
    if not paths:
        return
    print(f"  {len(paths)} {label}:")
    for p in paths[:SHOW_FILES]:
        print(f"    {symbol} {p}")
    if len(paths) > SHOW_FILES:
        print(f"    ... and {len(paths) - SHOW_FILES} more")


def update_index(cfg) -> None:
    """Index the data folder if anything changed. Never raises: the app starts either way."""
    from doctrace.indexer import run_ingest

    print(f"Data folder: {cfg.data_dir}")
    if not cfg.data_dir.is_dir():
        print(
            "\n[!] The data folder does not exist, so there is nothing to check.\n"
            "    Create it and put your files inside, or set DOCTRACE_DATA_DIR in .env.\n"
            "    Starting the app with the existing index (if any)."
        )
        return

    print("Checking for new, changed or deleted files ...")
    changes = find_changes(cfg)
    if not changes.needed:
        if changes.indexed:
            print(f"\n[OK] No new data: all {changes.indexed} files are already indexed.")
        else:
            print(
                "\n[OK] Nothing to index yet: the data folder has no supported files.\n"
                "     Add files to it, then click 'Update index' in the app."
            )
        if cfg.gdrive_folder_id:
            print("     (Google Drive is not checked here; run `python ingest.py --gdrive` to refresh it.)")
        return

    print()
    if changes.reason:
        print(f"[*] The whole index will be rebuilt because {changes.reason}.")
    elif not changes.indexed:
        print(f"[*] First-time indexing: {len(changes.new)} files found.")
    else:
        print("[*] Changes since the last run:")
        _list("+", "new", changes.new)
        _list("~", "changed", changes.changed)
        _list("-", "deleted (will be removed from the index)", changes.removed)

    print("\nUpdating the index before starting the app. You can stop with Ctrl+C at any time:")
    print("finished files are kept, and the next run continues where it stopped.\n")
    try:
        summary = run_ingest(cfg)
    except Exception as e:  # noqa: BLE001 - the app still opens with the existing index
        print(f"\n[!] Updating the index failed: {e}")
        print("    Starting the app with the existing index. Run `python doctor.py` for help.")
        return
    print("\n[OK] Index updated: " + summary.text())


def main() -> None:
    _use_project_venv()
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    try:
        _run()
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(130)
    except ModuleNotFoundError as e:
        sys.exit(
            f"\nMissing package: {e.name}. This Python doesn't have DocTrace installed.\n"
            "Run the setup first: double-click start.bat (Windows) or run `bash start.sh` (macOS/Linux)."
        )


def _run() -> None:
    from doctrace.config import ConfigError, load_settings

    print("=" * 60 + "\n DocTrace\n" + "=" * 60)
    try:
        cfg = load_settings()
    except ConfigError as e:
        sys.exit(f"Error: {e}\nFix that line in .env (or delete it to use the default) and try again.")

    update_index(cfg)

    if not {"-q", "--query"} & set(sys.argv[1:]):  # a one-off terminal search doesn't start the app
        print("\nStarting the search app (loading the search model takes a few seconds) ...")
        print("Stop it with Ctrl+C or by closing this window.\n")
    import search_app

    sys.argv = [str(ROOT / "search_app.py"), *sys.argv[1:]]
    search_app.main()


if __name__ == "__main__":
    main()
