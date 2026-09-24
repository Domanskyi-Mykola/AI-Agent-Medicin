"""Пошук релевантних чанків у базі знань: векторний (E5) + лексичний (BM25).

Два списки кандидатів зливаються через Reciprocal Rank Fusion (RRF):
векторний пошук ловить перефрази і синоніми, BM25 — точні терміни
(«Schatzker VI», «передня хрестоподібна зв'язка»), які на великій
однодоменній базі губляться серед загально схожих розділів.
Заміри (2026-09, 38 статей / 819 чанків, 32 питання з відомою статтею-відповіддю):
потрібна стаття в top-10 — векторний 29/32, BM25 31/32, RRF 32/32.
"""
from collections import defaultdict
from typing import Optional

from app.config import get_settings
from app.rag.embeddings import embed_queries
from app.rag.lexical import lexical_search
from app.rag.vector_store import Chunk, get_vector_store

_CANDIDATES = 30  # кандидатів з кожного пошуку до злиття
_RRF_K = 60       # стандартна константа RRF


def retrieve(query: str, top_k: Optional[int] = None) -> list[Chunk]:
    """Повертає релевантні чанки для питання.

    Порожній список означає «питання явно не про цю базу знань»: жоден чанк
    не пройшов поріг векторної відстані. Лексичні збіги в такому разі не
    рятують запит (слово «перелом» у питанні про погоду не робить його
    травматологічним). У строгому режимі тоді LLM не викликається взагалі.
    """
    s = get_settings()
    top_k = top_k or s.rag_top_k
    store = get_vector_store()
    if store.count() == 0:
        return []

    [embedding] = embed_queries([query])
    # Косинусна відстань = 1 - cos_sim; поріг відсікає явно нерелевантне
    # (значення підбирається під embedding-модель, див. .env.example).
    dense = [
        c for c in store.query(embedding, max(_CANDIDATES, top_k))
        if c.distance is None or c.distance <= s.rag_max_distance
    ]
    if not dense:
        return []

    score: dict[str, float] = defaultdict(float)
    by_id: dict[str, Chunk] = {}
    for rank, c in enumerate(dense):
        score[c.id] += 1.0 / (_RRF_K + rank)
        by_id[c.id] = c
    for rank, (c, _) in enumerate(lexical_search(query, _CANDIDATES)):
        score[c.id] += 1.0 / (_RRF_K + rank)
        by_id.setdefault(c.id, c)  # лише-лексичний збіг: distance = None

    best = sorted(score, key=score.get, reverse=True)[:top_k]
    return [by_id[i] for i in best]


def group_by_section(chunks: list[Chunk]) -> list[Chunk]:
    """Зливає чанки одного розділу однієї статті в один фрагмент.

    Інакше в тексті відповіді [1] і [5] вели на той самий розділ і лікар бачив
    «два джерела» там, де воно одне. Порядок — за найкращим рангом розділу,
    текст — у порядку чанків у статті.
    """
    groups: dict[tuple, list[Chunk]] = {}
    for c in chunks:
        key = (c.metadata.get("source_name"), c.metadata.get("section"))
        groups.setdefault(key, []).append(c)
    merged = []
    for parts in groups.values():
        parts.sort(key=lambda c: int(c.metadata.get("chunk_index", 0)))
        distances = [c.distance for c in parts if c.distance is not None]
        merged.append(Chunk(
            id="+".join(c.id for c in parts),
            text="\n\n".join(c.text for c in parts),
            metadata=parts[0].metadata,
            distance=min(distances) if distances else None,
        ))
    return merged
