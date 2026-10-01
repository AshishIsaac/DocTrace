"""Split text into overlapping chunks along paragraph / sentence boundaries."""
from __future__ import annotations

import re
from collections.abc import Iterator

_INLINE_WS = re.compile(r"[ \t\f\v ]+")
_BLANK_LINES = re.compile(r"\n\s*\n+")
_SENTENCE_END = re.compile(r"(?<=[.!?;:])\s+|\n")
_MIN_ALNUM = 3  # drop chunks that are just punctuation / page numbers


def normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = _INLINE_WS.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    return _BLANK_LINES.sub("\n\n", text).strip()


def _pieces(text: str, size: int) -> Iterator[str]:
    """Yield paragraphs, falling back to sentences / hard cuts, each <= size."""
    for para in text.split("\n\n"):
        if len(para) <= size:
            yield para
            continue
        for sent in _SENTENCE_END.split(para):
            sent = sent.strip()
            while len(sent) > size:
                cut = sent.rfind(" ", 0, size)
                if cut < size // 2:
                    cut = size
                yield sent[:cut].strip()
                sent = sent[cut:].strip()
            if sent:
                yield sent


def _tail(text: str, n: int) -> str:
    if n <= 0:
        return ""
    if len(text) <= n:
        return text
    tail = text[-n:]
    space = tail.find(" ")
    return tail[space + 1:] if space != -1 else tail


def chunk_text(text: str, size: int = 1000, overlap: int = 150) -> list[str]:
    text = normalize(text)
    chunks: list[str] = []
    cur = ""
    for piece in _pieces(text, size):
        if not piece:
            continue
        if cur and len(cur) + 1 + len(piece) > size:
            chunks.append(cur)
            tail = _tail(cur, overlap)
            cur = f"{tail} {piece}" if tail and len(tail) + 1 + len(piece) <= size else piece
        else:
            cur = f"{cur}\n{piece}" if cur else piece
    if cur:
        chunks.append(cur)
    return [c for c in chunks if sum(ch.isalnum() for ch in c) >= _MIN_ALNUM]
