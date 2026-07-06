"""Розбиття markdown-джерел на чанки з перекриттям.

Чанкінг за токенами embedding-моделі (≈500 токенів, перекриття ≈80). Межі
секцій (заголовки markdown) поважаються: чанк не перетинає заголовок, щоб
метадані `section` були коректні.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

CHUNK_TOKENS = 500
OVERLAP_TOKENS = 80


@dataclass
class RawChunk:
    text: str
    section: str


def _split_sections(markdown: str) -> list[tuple[str, str]]:
    """Ділить текст на (заголовок_секції, текст) за markdown-заголовками (#..######)."""
    lines = markdown.splitlines()
    sections: list[tuple[str, list[str]]] = []
    current_title = ""
    current_body: list[str] = []
    heading_re = re.compile(r"^#{1,6}\s+(.*)$")

    for line in lines:
        m = heading_re.match(line)
        if m:
            if current_body or current_title:
                sections.append((current_title, current_body))
            current_title = m.group(1).strip()
            current_body = []
        else:
            current_body.append(line)
    if current_body or current_title:
        sections.append((current_title, current_body))

    return [(title, "\n".join(body).strip()) for title, body in sections if "\n".join(body).strip()]


def chunk_markdown(markdown: str, tokenizer) -> list[RawChunk]:
    """Повертає чанки з прив'язкою до секції. tokenizer — з embedding-моделі."""
    chunks: list[RawChunk] = []
    for section_title, body in _split_sections(markdown):
        token_ids = tokenizer.encode(body, add_special_tokens=False)
        if not token_ids:
            continue
        step = CHUNK_TOKENS - OVERLAP_TOKENS
        for start in range(0, len(token_ids), step):
            window = token_ids[start : start + CHUNK_TOKENS]
            text = tokenizer.decode(window, skip_special_tokens=True).strip()
            if text:
                chunks.append(RawChunk(text=text, section=section_title))
            if start + CHUNK_TOKENS >= len(token_ids):
                break
    return chunks
