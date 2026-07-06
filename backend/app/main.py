"""Trauma AI — FastAPI-бекенд.

Запуск (з каталогу backend/, в активованому venv):
    uvicorn app.main:app --reload --port 8000
"""
from app.ssl_setup import enable_os_trust_store

enable_os_trust_store()  # до імпорту anthropic/httpx-клієнтів

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, documents, health

app = FastAPI(
    title="Trauma AI Assistant",
    description="MVP AI-асистента лікаря-травматолога: клінічний Q&A (RAG) + чернетки документації",
    version="0.1.0",
)

# CORS потрібен лише якщо фронтенд ходить напряму (без vite-proxy)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(chat.router, tags=["chat"])
app.include_router(documents.router, tags=["documents"])


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {
        "service": "trauma-ai backend",
        "docs": "/docs",
        "health": "/api/health",
    }
