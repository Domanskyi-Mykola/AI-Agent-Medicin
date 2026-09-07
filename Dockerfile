# --- Stage 1: збірка фронтенду (React + Vite) ---
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage 2: бекенд (FastAPI) + зібраний фронтенд ---
FROM python:3.12-slim AS runtime
WORKDIR /app/backend

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Кешуємо embedding-модель у шар образу (~1 ГБ), щоб контейнер не тягнув її
# з HuggingFace при кожному холодному старті — довше збирається, зате
# швидкий і надійний старт застосунку.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-base')"

COPY backend/ ./
COPY data/ /app/data/
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# Railway підставляє $PORT автоматично; локально (docker run без PORT) — 8000.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
