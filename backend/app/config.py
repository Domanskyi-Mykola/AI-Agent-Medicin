"""Конфігурація застосунку.

Всі значення можна перевизначити через змінні оточення або файл .env
у корені репозиторію (див. .env.example).
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> корінь репозиторію
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Claude API
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-5"
    max_answer_tokens: int = 2048
    max_document_tokens: int = 4096

    # Embeddings
    embedding_model: str = "intfloat/multilingual-e5-base"

    # Векторна БД (ChromaDB, локально)
    chroma_dir: str = str(REPO_ROOT / "storage" / "chroma")
    chroma_collection: str = "trauma_sources"

    # RAG
    rag_top_k: int = 5
    # Коса відстань (1 - cos_sim). Каліброване на прикладних джерелах для
    # multilingual-e5-base: релевантні запити дають 0.09-0.19, явно чужі
    # (погода) - 0.24+. Медично-суміжні (кардіологія ~0.19) відсіює вже LLM
    # за системним промптом, а не поріг. Див. docs/ARCHITECTURE.md.
    rag_max_distance: float = 0.22

    # Шляхи
    sources_dir: str = str(REPO_ROOT / "data" / "sources")
    audit_log_dir: str = str(REPO_ROOT / "logs")


@lru_cache
def get_settings() -> Settings:
    return Settings()
