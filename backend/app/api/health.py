"""GET /api/health — перевірка бекенда, векторної БД і доступності Claude API.

За замовчуванням ключ Anthropic перевіряється лише на наявність.
GET /api/health?deep=true додатково робить мінімальний реальний запит до
Claude API (коштує частки цента) — для перевірки, що ключ робочий.
"""
from fastapi import APIRouter

from app.config import get_settings
from app.llm.claude import LLMError, LLMNotConfigured, ask_claude
from app.rag.vector_store import get_vector_store

router = APIRouter()


@router.get("/api/health")
def health(deep: bool = False) -> dict:
    s = get_settings()
    checks: dict[str, dict] = {"backend": {"ok": True}}

    try:
        n = get_vector_store().count()
        checks["vector_store"] = {"ok": True, "chunks": n, "ingested": n > 0}
    except Exception as e:  # noqa: BLE001 — health не повинен падати
        checks["vector_store"] = {"ok": False, "error": str(e)}

    if not s.anthropic_api_key:
        checks["anthropic"] = {
            "ok": False,
            "configured": False,
            "error": "ANTHROPIC_API_KEY не заданий (див. .env.example)",
        }
    elif deep:
        try:
            _, usage = ask_claude(user="Відповідай одним словом: pong", max_tokens=8)
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
    return {"status": status, "model": s.claude_model, "checks": checks}
