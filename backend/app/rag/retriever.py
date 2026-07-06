"""Пошук релевантних чанків у базі знань."""
from typing import Optional

from app.config import get_settings
from app.rag.embeddings import embed_queries
from app.rag.vector_store import Chunk, get_vector_store


def retrieve(query: str, top_k: Optional[int] = None) -> list[Chunk]:
    """Повертає релевантні чанки для питання.

    Порожній список означає "у базі знань недостатньо даних" — у цьому
    випадку виклик LLM не робиться взагалі (RAG-grounded, без вільної
    генерації з пам'яті моделі).
    """
    s = get_settings()
    top_k = top_k or s.rag_top_k
    store = get_vector_store()
    if store.count() == 0:
        return []
    [embedding] = embed_queries([query])
    chunks = store.query(embedding, top_k)
    # Косинусна відстань = 1 - cos_sim. Поріг відсікає нерелевантні чанки;
    # значення підбирається під embedding-модель (див. .env.example).
    return [c for c in chunks if c.distance is None or c.distance <= s.rag_max_distance]
