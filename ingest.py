"""Build / update the search index.

    python ingest.py                  # index ./data (or DOCTRACE_DATA_DIR) incrementally
    python ingest.py --data-dir D:/Notes
    python ingest.py --rebuild        # drop everything and re-index from scratch
    python ingest.py --gdrive         # also index the Google Drive folder from .env

Only new or changed files are processed on each run; deleted files are removed.
Safe to stop with Ctrl+C - finished files are kept and the next run continues.
"""
from __future__ import annotations

import argparse
import sys

from doctrace.config import ConfigError, load_settings
from doctrace.indexer import run_ingest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", help="folder to index (default: DOCTRACE_DATA_DIR or ./data)")
    ap.add_argument("--rebuild", action="store_true", help="re-index everything from scratch")
    ap.add_argument("--gdrive", action="store_true", help="also index GDRIVE_FOLDER_ID")
    ap.add_argument("--no-local", action="store_true", help="skip the local data folder")
    args = ap.parse_args()

    try:
        cfg = load_settings(args.data_dir)
        summary = run_ingest(
            cfg, rebuild=args.rebuild, local_source=not args.no_local, gdrive=args.gdrive,
        )
    # RuntimeError covers IngestError and DOCTRACE_OCR=on without Tesseract; OSError a missing key file
    except (ConfigError, RuntimeError, OSError) as e:
        sys.exit(f"Error: {e}")

    print("\nDone: " + summary.text())
    if summary.chunks:
        print("\nNext: python search_app.py")
    elif not summary.interrupted:
        print(f"\nNothing to search yet - add files to {cfg.data_dir} and run this again.")


if __name__ == "__main__":
    main()
