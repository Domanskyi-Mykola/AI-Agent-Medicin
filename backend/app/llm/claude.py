"""Обгортка над Anthropic Claude API.

Примітка щодо моделі: claude-sonnet-5 не приймає temperature/top_p/top_k
(повертає 400), adaptive thinking увімкнений за замовчуванням — тому
передаємо лише model/max_tokens/system/messages.
"""
from functools import lru_cache
from typing import Optional

import anthropic

from app.config import get_settings


class LLMNotConfigured(Exception):
    """ANTHROPIC_API_KEY не заданий."""


class LLMError(Exception):
    """Помилка виклику Claude API (мережа, ліміти, невірний ключ тощо)."""

    def __init__(self, message: str, status_code: int = 502):
        self.status_code = status_code
        super().__init__(message)


@lru_cache
def _get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=get_settings().anthropic_api_key)


def ask_claude(user: str, system: Optional[str] = None, max_tokens: int = 2048) -> tuple[str, dict]:
    """Один запит до Claude. Повертає (текст відповіді, usage-метадані)."""
    s = get_settings()
    if not s.anthropic_api_key:
        raise LLMNotConfigured(
            "ANTHROPIC_API_KEY не заданий. Скопіюйте .env.example у .env і вкажіть ключ."
        )

    kwargs: dict = {
        "model": s.claude_model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": user}],
    }
    if system:
        kwargs["system"] = system

    try:
        response = _get_client().messages.create(**kwargs)
    except anthropic.AuthenticationError as e:
        raise LLMError("Невірний ANTHROPIC_API_KEY.", status_code=503) from e
    except anthropic.RateLimitError as e:
        raise LLMError(
            "Перевищено ліміт запитів до Claude API, спробуйте за хвилину.",
            status_code=429,
        ) from e
    except anthropic.APIConnectionError as e:
        raise LLMError("Немає з'єднання з Claude API.", status_code=502) from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"Помилка Claude API ({e.status_code}).", status_code=502) from e

    text = "".join(block.text for block in response.content if block.type == "text")
    usage = {
        "model": response.model,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "stop_reason": response.stop_reason,
    }
    return text, usage
