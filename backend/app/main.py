"""Trauma AI — FastAPI-бекенд.

Локальний запуск (з каталогу backend/, в активованому venv):
    uvicorn app.main:app --reload --port 8000

У продакшн-образі (Dockerfile) фронтенд уже зібраний (`frontend/dist`) і
цей самий процес віддає і API, і статичні файли — окремий сервер для
фронтенду не потрібен.
"""
from contextlib import asynccontextmanager

from app.ssl_setup import enable_os_trust_store

enable_os_trust_store()  # до імпорту anthropic/httpx-клієнтів

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import chat, documents, health
from app.config import REPO_ROOT

FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Якщо векторна БД порожня (перший запуск контейнера на чистому диску) —
    # наповнюємо її з data/sources/*.md автоматично. База зараз крихітна
    # (2 файли), тож це швидко; коли ingestion.ingest.ingest() матиме сенс
    # запускати окремим кроком деплою (реальні протоколи, великий обсяг) —
    # цю автоматичну заливку варто прибрати.
    from app.rag.vector_store import get_vector_store

    store = get_vector_store()
    if store.count() == 0:
        print("Векторна БД порожня — виконую первинний ingestion...")
        from ingestion.ingest import ingest

        ingest(reset=False)
    yield


app = FastAPI(
    title="Trauma AI Assistant",
    description="MVP AI-асистента лікаря-травматолога: клінічний Q&A (RAG) + чернетки документації",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS потрібен лише для локальної розробки (фронтенд на vite dev-сервері,
# інший порт). У продакшн-образі фронтенд і API — той самий origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(chat.router, tags=["chat"])
app.include_router(documents.router, tags=["documents"])

if FRONTEND_DIST.is_dir():
    # Продакшн: фронтенд зібраний (Dockerfile) — віддаємо його з цього ж процесу.
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def serve_index() -> FileResponse:
        return FileResponse(FRONTEND_DIST / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str) -> FileResponse:
        # Будь-який невідомий GET-шлях (крім /api/*, /docs — вони вже
        # оброблені роутерами й FastAPI вище) -> index.html.
        candidate = FRONTEND_DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")

else:
    # Локальна розробка без збірки фронтенду: фронтенд піднятий окремо
    # (npm run dev, :5173) і ходить сюди через vite-proxy.
    @app.get("/", include_in_schema=False)
    def root() -> dict:
        return {
            "service": "trauma-ai backend",
            "docs": "/docs",
            "health": "/api/health",
        }
