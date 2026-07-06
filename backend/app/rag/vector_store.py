"""Абстракція над векторною БД.

Для MVP використовується локальна ChromaDB. Інтерфейс VectorStore навмисно
мінімальний, щоб пізніше замінити Chroma на pgvector/Pinecone без змін у
retriever та ingestion.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Optional

import chromadb

from app.config import get_settings


@dataclass
class Chunk:
    id: str
    text: str
    metadata: dict
    distance: Optional[float] = None


class VectorStore(ABC):
    @abstractmethod
    def add(
        self,
        ids: Iterable[str],
        texts: Iterable[str],
        embeddings: Iterable[list[float]],
        metadatas: Iterable[dict],
    ) -> None:
        """Додає (або оновлює за id) чанки з готовими ембедингами."""

    @abstractmethod
    def query(self, embedding: list[float], top_k: int) -> list[Chunk]:
        """Повертає top_k найближчих чанків (відстань — косинусна)."""

    @abstractmethod
    def count(self) -> int: ...

    @abstractmethod
    def reset(self) -> None:
        """Повністю очищає колекцію (для повторного ingestion)."""


class ChromaVectorStore(VectorStore):
    def __init__(self, path: str, collection: str):
        self._client = chromadb.PersistentClient(path=path)
        self._collection_name = collection
        self._collection = self._client.get_or_create_collection(
            name=collection, metadata={"hnsw:space": "cosine"}
        )

    def add(self, ids, texts, embeddings, metadatas) -> None:
        # upsert — повторний ingestion того самого файла оновлює чанки, а не падає
        self._collection.upsert(
            ids=list(ids),
            documents=list(texts),
            embeddings=[list(e) for e in embeddings],
            metadatas=list(metadatas),
        )

    def query(self, embedding: list[float], top_k: int) -> list[Chunk]:
        n_results = min(top_k, max(self.count(), 1))
        res = self._collection.query(
            query_embeddings=[list(embedding)],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )
        chunks: list[Chunk] = []
        for i, chunk_id in enumerate(res["ids"][0]):
            chunks.append(
                Chunk(
                    id=chunk_id,
                    text=res["documents"][0][i],
                    metadata=res["metadatas"][0][i] or {},
                    distance=res["distances"][0][i],
                )
            )
        return chunks

    def count(self) -> int:
        return self._collection.count()

    def reset(self) -> None:
        self._client.delete_collection(self._collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name, metadata={"hnsw:space": "cosine"}
        )


@lru_cache
def get_vector_store() -> VectorStore:
    s = get_settings()
    return ChromaVectorStore(path=s.chroma_dir, collection=s.chroma_collection)
