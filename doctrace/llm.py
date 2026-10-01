"""Optional answer generation with a local Ollama model."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import requests

from .config import Settings
from .search import Hit

MAX_CONTEXT_CHARS = 6000

PROMPT = """You are a helpful assistant answering questions about the user's own files.
Use ONLY the numbered sources below. Cite sources inline like [1] or [2][3].
If the sources do not contain the answer, say you could not find it in the files.

{sources}

Question: {question}
Answer:"""


def find_ollama() -> str:
    """Path to the ollama executable, or '' if it is not installed."""
    found = shutil.which("ollama")
    if found:
        return found
    candidates = []
    if sys.platform == "win32":
        candidates.append(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe")
    elif sys.platform == "darwin":
        candidates.append(Path("/Applications/Ollama.app/Contents/Resources/ollama"))
    return next((str(p) for p in candidates if p.is_file()), "")


class Ollama:
    def __init__(self, cfg: Settings):
        self.url = cfg.ollama_url
        self.model = cfg.ollama_model
        self.autostart = cfg.ollama_autostart and cfg.ollama_url.startswith(
            ("http://localhost", "http://127.0.0.1"))
        self._started = False

    def _get(self, path: str, timeout: float = 3):
        r = requests.get(f"{self.url}{path}", timeout=timeout)
        r.raise_for_status()
        return r.json()

    def running(self) -> bool:
        try:
            self._get("/api/tags")
            return True
        except requests.RequestException:
            return False

    def ensure_running(self) -> bool:
        """Start `ollama serve` in the background if it is installed but not running."""
        if self.running():
            return True
        exe = find_ollama()
        if not (self.autostart and exe) or self._started:
            return False
        self._started = True
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        subprocess.Popen(
            [exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, creationflags=flags, start_new_session=sys.platform != "win32",
        )
        for _ in range(30):
            time.sleep(0.5)
            if self.running():
                return True
        return False

    def has_model(self) -> bool:
        try:
            names = {m.get("name", "") for m in self._get("/api/tags").get("models", [])}
        except requests.RequestException:
            return False
        return any(n == self.model or n.split(":")[0] == self.model for n in names)

    def status(self) -> str:
        """Empty string if ready, otherwise a human-readable reason."""
        if not self.ensure_running():
            if not find_ollama():
                return "Install Ollama from https://ollama.com to get written answers (search works without it)."
            return f"Ollama is not running at {self.url} (start it with `ollama serve`)."
        if not self.has_model():
            return f"The model '{self.model}' is not downloaded yet."
        return ""

    def pull(self) -> Iterator[str]:
        """Download the model, yielding human-readable progress lines."""
        with requests.post(f"{self.url}/api/pull", json={"model": self.model, "stream": True},
                           stream=True, timeout=(5, 3600)) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                if data.get("error"):
                    raise RuntimeError(data["error"])
                msg = data.get("status", "")
                if data.get("total") and data.get("completed") is not None:
                    pct = 100 * data["completed"] / data["total"]
                    msg = f"{msg} {pct:.0f}% of {data['total'] / 1e9:.1f} GB"
                yield msg

    def answer(self, question: str, hits: list[Hit]) -> Iterator[str]:
        """Stream the answer text, token by token."""
        prompt = PROMPT.format(sources=format_sources(hits), question=question)
        with requests.post(
            f"{self.url}/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": True,
                  "options": {"temperature": 0.2}},
            stream=True, timeout=(5, 300),
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                if data.get("error"):
                    raise RuntimeError(data["error"])
                yield data.get("response", "")
                if data.get("done"):
                    return


def context_hits(hits: list[Hit], limit: int = 6) -> list[Hit]:
    out, used = [], 0
    for h in hits:
        if len(out) >= limit or used + len(h.chunk.text) > MAX_CONTEXT_CHARS:
            break
        out.append(h)
        used += len(h.chunk.text)
    return out


def format_sources(hits: list[Hit]) -> str:
    parts = []
    for i, h in enumerate(hits, start=1):
        loc = f", {h.chunk.location}" if h.chunk.location else ""
        parts.append(f"[{i}] {h.chunk.path}{loc}\n{h.chunk.text}")
    return "\n\n".join(parts)
