"""Check that everything DocTrace needs is installed and working.

    python doctor.py                   # run all checks, print fixes for anything missing
    python doctor.py --download-model  # also download the embedding model now (used by setup)
    python doctor.py --pull-ollama-model   # download the Ollama model from .env (OLLAMA_MODEL)
"""
from __future__ import annotations

import argparse
import importlib
import sqlite3
import sys
from collections import Counter
from pathlib import Path

OK, WARN, FAIL = "  OK ", "WARN ", "FAIL "
problems = {"fail": 0, "warn": 0}


def report(level: str, msg: str, fix: str = "") -> None:
    if level == FAIL:
        problems["fail"] += 1
    elif level == WARN:
        problems["warn"] += 1
    print(f"[{level}] {msg}")
    if fix:
        print(f"         -> {fix}")


def check_python() -> None:
    v = sys.version_info
    if v < (3, 10):
        report(FAIL, f"Python {v.major}.{v.minor}", "Install Python 3.10 - 3.13 from https://python.org")
    else:
        report(OK, f"Python {v.major}.{v.minor}.{v.micro}")
    if sys.prefix == sys.base_prefix:
        report(WARN, "Not running inside a virtual environment",
               "Activate it first: .venv\\Scripts\\activate (Windows) or source .venv/bin/activate")


PACKAGES = [
    ("sentence_transformers", "sentence-transformers", True),
    ("faiss", "faiss-cpu", True),
    ("numpy", "numpy", True),
    ("gradio", "gradio", True),
    ("requests", "requests", True),
    ("tqdm", "tqdm", True),
    ("pymupdf", "pymupdf", True),
    ("docx", "python-docx", True),
    ("pptx", "python-pptx", True),
    ("openpyxl", "openpyxl", True),
    ("PIL", "pillow", True),
    ("pytesseract", "pytesseract", False),
    ("dotenv", "python-dotenv", False),
]


def check_packages() -> bool:
    missing = []
    for module, pip_name, required in PACKAGES:
        try:
            mod = importlib.import_module(module)
            version = getattr(mod, "__version__", "") or getattr(mod, "VersionBind", "")
            report(OK, f"{pip_name} {version}".strip())
        except Exception as e:  # noqa: BLE001 - broken installs raise all sorts of errors
            if required:
                missing.append(pip_name)
                report(FAIL, f"{pip_name} is not importable ({type(e).__name__}: {e})")
            else:
                report(WARN, f"{pip_name} is not installed (optional)")
    if missing:
        print("         -> pip install -r requirements.txt")
    return not missing


def check_torch() -> None:
    try:
        import torch
    except Exception as e:  # noqa: BLE001
        report(FAIL, f"torch is not importable ({e})", "Re-run the setup script")
        return
    if torch.cuda.is_available():
        report(OK, f"torch {torch.__version__} using GPU: {torch.cuda.get_device_name(0)}")
    elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        report(OK, f"torch {torch.__version__} using Apple GPU (MPS)")
    else:
        report(OK, f"torch {torch.__version__} on CPU (fine; a GPU only speeds up indexing)")


def check_sqlite() -> None:
    try:
        sqlite3.connect(":memory:").execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        report(OK, f"SQLite {sqlite3.sqlite_version} with full-text search")
    except sqlite3.OperationalError:
        report(WARN, "SQLite has no FTS5: keyword search is disabled (semantic search still works)",
               "Use the official Python build from python.org")


def check_model(cfg, download: bool) -> None:
    from doctrace.embed import Embedder, load_model

    try:
        load_model(cfg.embed_model, local_only=True)
        report(OK, f"Embedding model cached: {cfg.embed_model}")
        return
    except Exception:  # noqa: BLE001
        pass
    if not download:
        report(WARN, f"Embedding model not downloaded yet: {cfg.embed_model}",
               "It downloads automatically on first use, or run: python doctor.py --download-model")
        return
    print(f"         downloading {cfg.embed_model} ...")
    try:
        Embedder(cfg.embed_model).encode(["test"])
        report(OK, f"Embedding model downloaded: {cfg.embed_model}")
    except Exception as e:  # noqa: BLE001
        report(FAIL, f"Could not download {cfg.embed_model}: {e}",
               "Check your internet connection / proxy, then run: python doctor.py --download-model")


def check_ocr(cfg) -> None:
    from doctrace.extract import configure_ocr

    if cfg.ocr == "off":
        report(OK, "OCR disabled (DOCTRACE_OCR=off)")
        return
    try:
        if configure_ocr("auto", cfg.tesseract_cmd):
            import pytesseract

            report(OK, f"Tesseract OCR {pytesseract.get_tesseract_version()}")
            return
    except Exception:  # noqa: BLE001
        pass
    fix = {
        "win32": "winget install UB-Mannheim.TesseractOCR  (or set TESSERACT_CMD in .env)",
        "darwin": "brew install tesseract",
    }.get(sys.platform, "sudo apt install tesseract-ocr")
    report(WARN, "Tesseract not found: images and scanned PDFs will be skipped", fix)


def check_ollama(cfg) -> None:
    from doctrace.llm import Ollama, find_ollama

    if cfg.llm == "none":
        report(OK, "Answer generation disabled (DOCTRACE_LLM=none)")
        return
    llm = Ollama(cfg)
    if not find_ollama() and not llm.running():
        fix = {"win32": "winget install Ollama.Ollama", "darwin": "brew install --cask ollama"}.get(
            sys.platform, "curl -fsSL https://ollama.com/install.sh | sh")
        report(WARN, "Ollama not installed: search works, but no written answers", fix)
        return
    if not llm.ensure_running():
        report(WARN, f"Ollama is installed but not reachable at {cfg.ollama_url}", "Run: ollama serve")
        return
    if not llm.has_model():
        report(WARN, f"Ollama model '{cfg.ollama_model}' not downloaded",
               f"ollama pull {cfg.ollama_model}  (or use the button in the app)")
        return
    report(OK, f"Ollama running with model '{cfg.ollama_model}'")


def check_data(cfg) -> None:
    from doctrace.local import scan

    if not cfg.data_dir.is_dir():
        report(FAIL, f"Data folder does not exist: {cfg.data_dir}",
               "Create it and add files, or set DOCTRACE_DATA_DIR in .env")
        return
    records, _ = scan(cfg.data_dir, cfg.index_dir, cfg.max_file_mb)
    if not records:
        report(WARN, f"No supported files in {cfg.data_dir}", "Copy your documents into it")
        return
    kinds = Counter(Path(r.path).suffix.lower() for r in records)
    top = ", ".join(f"{n} {ext}" for ext, n in kinds.most_common(6))
    report(OK, f"{len(records)} files in {cfg.data_dir} ({top})")


def check_index(cfg) -> None:
    db = cfg.index_dir / "doctrace.sqlite"
    if not db.exists():
        report(WARN, "No index yet", "Run: python ingest.py  (or click 'Update index' in the app)")
        return
    from doctrace.store import Store

    store = Store(cfg.index_dir)
    st = store.stats()
    model = store.get_meta("embed_model")
    store.close()
    if not st["chunks"]:
        report(WARN, "The index is empty", "Run: python ingest.py")
    elif model and model != cfg.embed_model:
        report(WARN, f"Index was built with {model}, .env says {cfg.embed_model}",
               "Run: python ingest.py  (it re-indexes automatically)")
    else:
        report(OK, f"Index: {st['files']} files, {st['chunks']} passages ({st['skipped']} without text)")


def pull_ollama_model() -> None:
    from doctrace.config import load_settings
    from doctrace.llm import Ollama

    llm = Ollama(load_settings())
    if not llm.ensure_running():
        sys.exit(f"Ollama is not reachable at {llm.url}. Start it (ollama serve) and try again.")
    last = ""
    for msg in llm.pull():
        if msg != last:
            print("\r   " + msg.ljust(60), end="", flush=True)
            last = msg
    print(f"\n   {llm.model} is ready.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--download-model", action="store_true", help="download the embedding model")
    ap.add_argument("--pull-ollama-model", action="store_true", help="download the Ollama model")
    args = ap.parse_args()
    if args.pull_ollama_model:
        pull_ollama_model()
        return

    print("DocTrace - environment check\n")
    check_python()
    if not check_packages():
        sys.exit(1)
    check_torch()
    check_sqlite()

    from doctrace.config import ConfigError, ROOT, load_settings

    if not (ROOT / ".env").exists():
        report(WARN, "No .env file (defaults are used)", "copy .env.example .env  to customise settings")
    try:
        cfg = load_settings()
    except ConfigError as e:
        report(FAIL, str(e), "Fix the value in .env")
        sys.exit(1)
    check_model(cfg, args.download_model)
    check_ocr(cfg)
    check_ollama(cfg)
    check_data(cfg)
    check_index(cfg)

    print()
    if problems["fail"]:
        print(f"{problems['fail']} problem(s) must be fixed before DocTrace can run.")
        sys.exit(1)
    print("Ready." + (f" ({problems['warn']} optional item(s) above.)" if problems["warn"] else ""))


if __name__ == "__main__":
    main()
