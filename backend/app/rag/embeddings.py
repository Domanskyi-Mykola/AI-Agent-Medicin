"""Обгортка над sentence-transformers.

Моделі сімейства E5 (intfloat/multilingual-e5-*) вимагають префікси
"query: " для запитів і "passage: " для документів — без них якість
пошуку помітно падає.
"""
from functools import lru_cache

from app.config import get_settings


@lru_cache
def _get_model():
    # Важкий імпорт (torch) — робимо ліниво; у продакшні модель прогрівається
    # на старті (main.py, lifespan), щоб перший запит лікаря не чекав завантаження.
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(get_settings().embedding_model)


def is_loaded() -> bool:
    return _get_model.cache_info().currsize > 0


def get_tokenizer():
    """Токенізатор embedding-моделі — використовується для чанкінгу в ingestion."""
    return _get_model().tokenizer


def embed_queries(texts: list[str]) -> list[list[float]]:
    model = _get_model()
    vectors = model.encode(
        [f"query: {t}" for t in texts], normalize_embeddings=True
    )
    return [v.tolist() for v in vectors]


def embed_passages(texts: list[str]) -> list[list[float]]:
    model = _get_model()
    vectors = model.encode(
        [f"passage: {t}" for t in texts],
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    return [v.tolist() for v in vectors]
