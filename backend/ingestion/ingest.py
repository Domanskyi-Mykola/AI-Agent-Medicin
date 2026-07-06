"""Ingestion: markdown-джерела -> чанки -> ембединги -> ChromaDB.

Кожен файл у data/sources/ може мати YAML front-matter з метаданими:

    ---
    source_name: Класифікація AO/OTA
    document_number: AO/OTA-2018
    date: 2018
    ---
    # Заголовок ...

Без front-matter source_name = ім'я файлу.

Запуск (з каталогу backend/, у venv):
    python -m ingestion.ingest             # інкрементально (upsert)
    python -m ingestion.ingest --reset     # очистити колекцію і залити заново
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import yaml

from app.ssl_setup import enable_os_trust_store

enable_os_trust_store()  # до завантаження моделі з HuggingFace

from app.config import get_settings
from app.rag.embeddings import embed_passages, get_tokenizer
from app.rag.vector_store import get_vector_store
from ingestion.chunker import chunk_markdown


def _parse_front_matter(raw: str, fallback_name: str) -> tuple[dict, str]:
    """Витягує YAML front-matter (якщо є). Повертає (метадані, тіло)."""
    meta = {"source_name": fallback_name}
    body = raw
    if raw.startswith("---"):
        end = raw.find("\n---", 3)
        if end != -1:
            front = raw[3:end].strip()
            body = raw[end + 4 :].lstrip("\n")
            parsed = yaml.safe_load(front) or {}
            for k, v in parsed.items():
                meta[k] = str(v)
    return meta, body


def ingest(reset: bool = False) -> int:
    s = get_settings()
    sources_dir = Path(s.sources_dir)
    if not sources_dir.exists():
        raise SystemExit(f"Каталог джерел не знайдено: {sources_dir}")

    files = sorted(sources_dir.glob("*.md"))
    if not files:
        raise SystemExit(f"У {sources_dir} немає .md файлів.")

    store = get_vector_store()
    if reset:
        store.reset()
        print("Колекцію очищено (--reset).")

    tokenizer = get_tokenizer()
    total = 0

    for file in files:
        raw = file.read_text(encoding="utf-8")
        meta, body = _parse_front_matter(raw, fallback_name=file.stem)
        raw_chunks = chunk_markdown(body, tokenizer)
        if not raw_chunks:
            print(f"  {file.name}: чанків не отримано, пропускаю.")
            continue

        texts = [c.text for c in raw_chunks]
        # Детермінований id за (файл, індекс, хеш тексту): повторний ingest
        # оновлює той самий чанк замість дублювання.
        ids = [
            f"{file.stem}-{i}-{hashlib.sha1(c.text.encode('utf-8')).hexdigest()[:8]}"
            for i, c in enumerate(raw_chunks)
        ]
        metadatas = [{**meta, "section": c.section, "chunk_index": i} for i, c in enumerate(raw_chunks)]

        embeddings = embed_passages(texts)
        store.add(ids=ids, texts=texts, embeddings=embeddings, metadatas=metadatas)
        total += len(raw_chunks)
        print(f"  {file.name}: {len(raw_chunks)} чанків -> '{meta['source_name']}'")

    print(f"\nГотово. Усього чанків у колекції: {store.count()} (додано/оновлено цього запуску: {total}).")
    return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Залити джерела в векторну БД")
    parser.add_argument("--reset", action="store_true", help="очистити колекцію перед заливкою")
    args = parser.parse_args()
    ingest(reset=args.reset)
