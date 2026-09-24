"""GET /api/health — перевірка бекенда, векторної БД, embedding-моделі і Claude API.

За замовчуванням ключ Anthropic перевіряється лише на наявність.
GET /api/health?deep=true додатково робить реальний пошуковий ембединг і
мінімальний реальний запит до Claude API (коштує частки цента) — тобто
проходить ті самі важкі кроки, що й справжнє питання лікаря. Саме такий
чек треба робити перед показом: поверхневий health колись був «зеленим»,
поки справжні питання падали через брак пам'яті.
"""
from fastapi import APIRouter

from app.config import get_settings
from app.llm.claude import LLMError, LLMNotConfigured, ask_claude
from app.rag import embeddings
from app.rag.vector_store import get_vector_store
from app.sysinfo import memory_limit_mb, rss_mb

router = APIRouter()


@router.get("/api/health")
def health(deep: bool = False) -> dict:
    s = get_settings()
    checks: dict[str, dict] = {"backend": {"ok": True}}

    try:
        n = get_vector_store().count()
        checks["vector_store"] = {"ok": n > 0, "chunks": n, "ingested": n > 0}
    except Exception as e:  # noqa: BLE001 — health не повинен падати
        checks["vector_store"] = {"ok": False, "error": str(e)}

    if deep:
        try:
            vec = embeddings.embed_queries(["перелом"])[0]
            checks["embeddings"] = {"ok": len(vec) > 0, "model": s.embedding_model}
        except Exception as e:  # noqa: BLE001
            checks["embeddings"] = {"ok": False, "error": str(e)}
    else:
        checks["embeddings"] = {"ok": True, "loaded": embeddings.is_loaded()}

    if not s.anthropic_api_key:
        checks["anthropic"] = {
            "ok": False,
            "configured": False,
            "error": "ANTHROPIC_API_KEY не заданий (див. .env.example)",
        }
    elif deep:
        try:
            _, usage = ask_claude(user="Відповідай одним словом: pong", max_tokens=32, thinking=False)
            checks["anthropic"] = {"ok": True, "configured": True, "model": usage["model"]}
        except (LLMNotConfigured, LLMError) as e:
            checks["anthropic"] = {"ok": False, "configured": True, "error": str(e)}
    else:
        checks["anthropic"] = {
            "ok": True,
            "configured": True,
            "note": "перевірено лише наявність ключа; ?deep=true — реальний запит",
        }

    status = "ok" if all(c.get("ok") for c in checks.values()) else "degraded"
    return {
        "status": status,
        "model": s.claude_model,
        "answer_mode": s.answer_mode,
        "memory": {"rss_mb": rss_mb(), "limit_mb": memory_limit_mb()},
        "checks": checks,
    }
