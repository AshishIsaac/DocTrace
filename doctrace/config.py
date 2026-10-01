"""Settings, read from environment variables (and an optional .env file)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:  # python-dotenv is optional
    pass


def _env(name: str, default: str = "") -> str:
    value = os.environ.get(name, "").strip()
    return value if value else default


def _flag(name: str, default: bool) -> bool:
    value = _env(name, "1" if default else "0").lower()
    return value in {"1", "true", "yes", "on"}


class ConfigError(ValueError):
    pass


def _num(name: str, default: str, kind=int):
    raw = _env(name, default)
    try:
        return kind(raw)
    except ValueError:
        raise ConfigError(f"{name}={raw!r} in .env is not a valid number.") from None


def _path(value: str) -> Path:
    p = Path(value).expanduser()
    return (p if p.is_absolute() else ROOT / p).resolve()


@dataclass
class Settings:
    data_dir: Path
    index_dir: Path
    embed_model: str
    chunk_size: int
    chunk_overlap: int
    max_file_mb: float
    workers: int
    ocr: str  # auto | on | off
    tesseract_cmd: str
    llm: str  # auto | ollama | none
    ollama_url: str
    ollama_model: str
    host: str
    port: int
    allow_open: bool
    watch_minutes: float
    ollama_autostart: bool
    gdrive_folder_id: str
    gdrive_credentials: Path


def load_settings(data_dir: str | None = None) -> Settings:
    cfg = Settings(
        data_dir=_path(data_dir or _env("DOCTRACE_DATA_DIR", "data")),
        index_dir=_path(_env("DOCTRACE_INDEX_DIR", "vector_db")),
        embed_model=_env("DOCTRACE_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        chunk_size=_num("DOCTRACE_CHUNK_SIZE", "1000"),
        chunk_overlap=_num("DOCTRACE_CHUNK_OVERLAP", "150"),
        max_file_mb=_num("DOCTRACE_MAX_FILE_MB", "200", float),
        workers=_num("DOCTRACE_WORKERS", str(max(1, min(8, (os.cpu_count() or 2) - 1)))),
        ocr=_env("DOCTRACE_OCR", "auto").lower(),
        tesseract_cmd=_env("TESSERACT_CMD"),
        llm=_env("DOCTRACE_LLM", "auto").lower(),
        ollama_url=_env("OLLAMA_URL", "http://localhost:11434").rstrip("/"),
        ollama_model=_env("OLLAMA_MODEL", "llama3.2"),
        host=_env("DOCTRACE_HOST", "127.0.0.1"),
        port=_num("DOCTRACE_PORT", "7860"),
        allow_open=_flag("DOCTRACE_ALLOW_OPEN", True),
        watch_minutes=_num("DOCTRACE_WATCH_MINUTES", "0", float),
        ollama_autostart=_flag("OLLAMA_AUTOSTART", True),
        gdrive_folder_id=_env("GDRIVE_FOLDER_ID"),
        gdrive_credentials=_path(_env("GDRIVE_CREDENTIALS", "service_account.json")),
    )
    if cfg.ocr not in {"auto", "on", "off"}:
        raise ConfigError(f"DOCTRACE_OCR must be auto, on or off (got {cfg.ocr!r}).")
    if cfg.llm not in {"auto", "ollama", "none"}:
        raise ConfigError(f"DOCTRACE_LLM must be auto, ollama or none (got {cfg.llm!r}).")
    if not 0 <= cfg.chunk_overlap < cfg.chunk_size:
        raise ConfigError("DOCTRACE_CHUNK_OVERLAP must be smaller than DOCTRACE_CHUNK_SIZE.")
    cfg.workers = max(1, cfg.workers)
    return cfg
