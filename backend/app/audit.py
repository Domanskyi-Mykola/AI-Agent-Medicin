"""Аудит-лог викликів LLM.

Кожен виклик Claude API (і кожна відмова через порожній retrieval) пишеться
в локальний JSONL-файл logs/audit-YYYY-MM-DD.jsonl для подальшого контролю
якості відповідей.

УВАГА (безпека): у лог НЕ можна писати дані, що ідентифікують пацієнта
(ПІБ, дати народження, номери карт). Логуються лише текст запиту лікаря,
знайдені джерела та відповідь моделі. Відповідальність за відсутність
персональних даних у самому запиті — на рівні UI (попередження лікарю)
та політики використання.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings


def log_llm_call(endpoint: str, payload: dict) -> None:
    s = get_settings()
    log_dir = Path(s.audit_log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    record = {"ts": now.isoformat(), "endpoint": endpoint, **payload}
    path = log_dir / f"audit-{now:%Y-%m-%d}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
