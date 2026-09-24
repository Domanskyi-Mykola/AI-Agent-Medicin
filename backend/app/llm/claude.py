"""Обгортка над Anthropic Claude API.

Примітки щодо claude-sonnet-5:
- temperature/top_p/top_k не приймаються (400) — не передаємо;
- adaptive thinking увімкнене за замовчуванням, і max_tokens — СПІЛЬНИЙ бюджет
  на міркування і текст відповіді. Тому режим міркувань і effort задаємо явно,
  а причину зупинки (max_tokens / refusal) обробляємо, щоб не віддати лікарю
  обрізану або порожню відповідь без пояснень.

Стійкість (2026-09): зрідка модель «задумується» надовго — зафіксовано 7820 з
8000 токенів і 115 с на одне питання чату. Щоб лікар не отримав помилку, при
вичерпанні ліміту, таймауті чи порожній/зламаній відповіді робимо ОДНУ швидку
повторну спробу без міркувань. Бюджет часу: перша спроба ≤ CLAUDE_TIMEOUT_SECONDS
(80 с), швидка ≤ 50 с — разом менше за таймаут фронтенду (150 с). Короткі
збої API (перевантаження 529, 5xx, обрив з'єднання) повторюємо один раз;
таймаути SDK не повторює — інакше 3 × таймаут перевищили б очікування лікаря.
"""
import json
import time
from functools import lru_cache
from typing import Any, Optional

import anthropic

from app.config import get_settings

_FAST_RETRY_TIMEOUT = 50.0


class LLMNotConfigured(Exception):
    """ANTHROPIC_API_KEY не заданий."""


class LLMError(Exception):
    """Помилка виклику Claude API (мережа, ліміти, невірний ключ тощо).

    retry_fast=True — помилка, яку може виправити швидка повторна спроба
    без міркувань (вичерпаний ліміт токенів, таймаут, порожня відповідь).
    """

    def __init__(self, message: str, status_code: int = 502, retry_fast: bool = False):
        self.status_code = status_code
        self.retry_fast = retry_fast
        super().__init__(message)


@lru_cache
def _get_client() -> anthropic.Anthropic:
    s = get_settings()
    return anthropic.Anthropic(
        api_key=s.anthropic_api_key,
        timeout=s.claude_timeout_seconds,
        max_retries=0,  # повтори — власні, див. _create()
    )


def _create(kwargs: dict, timeout: Optional[float]):
    """messages.create з одним повтором для коротких збоїв (не для таймаутів)."""
    client = _get_client()
    if timeout is not None:
        kwargs = {**kwargs, "timeout": timeout}
    for attempt in range(2):
        try:
            return client.messages.create(**kwargs)
        except anthropic.APITimeoutError:
            raise
        except (anthropic.APIConnectionError, anthropic.InternalServerError, anthropic.OverloadedError):
            if attempt == 0:
                time.sleep(2)
                continue
            raise


def ask_claude(
    user: str,
    system: Optional[str] = None,
    max_tokens: int = 4096,
    *,
    json_schema: Optional[dict] = None,
    effort: Optional[str] = None,
    thinking: bool = True,
) -> tuple[Any, dict]:
    """Запит до Claude зі швидкою повторною спробою (див. docstring модуля).

    Повертає (результат, usage). Якщо передано json_schema — результат уже
    розібраний dict (structured outputs гарантують валідний JSON за схемою),
    інакше — рядок з текстом відповіді. Якщо спрацювала повторна спроба,
    usage["fallback"] містить причину.
    """
    try:
        return _ask_once(user, system, max_tokens, json_schema=json_schema, effort=effort, thinking=thinking)
    except LLMError as e:
        if not (e.retry_fast and thinking):
            raise
        result, usage = _ask_once(
            user, system, max_tokens, json_schema=json_schema, effort="low", thinking=False,
            timeout=_FAST_RETRY_TIMEOUT,
        )
        usage["fallback"] = str(e)
        return result, usage


def _ask_once(
    user: str,
    system: Optional[str],
    max_tokens: int,
    *,
    json_schema: Optional[dict],
    effort: Optional[str],
    thinking: bool,
    timeout: Optional[float] = None,
) -> tuple[Any, dict]:
    s = get_settings()
    if not s.anthropic_api_key:
        raise LLMNotConfigured(
            "ANTHROPIC_API_KEY не заданий. Скопіюйте .env.example у .env і вкажіть ключ."
        )

    kwargs: dict = {
        "model": s.claude_model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": user}],
        "thinking": {"type": "adaptive"} if thinking else {"type": "disabled"},
    }
    if system:
        kwargs["system"] = system
    output_config: dict = {}
    if effort:
        output_config["effort"] = effort
    if json_schema:
        output_config["format"] = {"type": "json_schema", "schema": json_schema}
    if output_config:
        kwargs["output_config"] = output_config

    try:
        response = _create(kwargs, timeout)
    except anthropic.AuthenticationError as e:
        raise LLMError("Невірний ANTHROPIC_API_KEY.", status_code=503) from e
    except anthropic.PermissionDeniedError as e:
        raise LLMError("Ключ Anthropic не має доступу до цієї моделі.", status_code=503) from e
    except anthropic.RateLimitError as e:
        raise LLMError(
            "Перевищено ліміт запитів до Claude API, спробуйте за хвилину.",
            status_code=429,
        ) from e
    except anthropic.APITimeoutError as e:
        raise LLMError(
            "Claude API не відповів вчасно. Спробуйте ще раз або звузьте питання.",
            status_code=504,
            retry_fast=True,
        ) from e
    except anthropic.APIConnectionError as e:
        raise LLMError("Немає з'єднання з Claude API.", status_code=502) from e
    except anthropic.BadRequestError as e:
        # Найчастіша причина на практиці — вичерпаний баланс API-ключа.
        msg = getattr(e, "message", "") or str(e)
        if "credit" in msg.lower() or "balance" in msg.lower():
            raise LLMError(
                "На рахунку Anthropic API закінчились кошти — поповніть баланс у консолі Anthropic.",
                status_code=503,
            ) from e
        raise LLMError(f"Некоректний запит до Claude API: {msg[:200]}", status_code=502) from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"Помилка Claude API ({e.status_code}).", status_code=502) from e

    usage = {
        "model": response.model,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "stop_reason": response.stop_reason,
    }

    if response.stop_reason == "refusal":
        raise LLMError(
            "Модель відмовилась відповідати на цей запит (спрацював фільтр безпеки). "
            "Спробуйте переформулювати питання.",
            status_code=422,
        )

    text = "".join(block.text for block in response.content if block.type == "text")

    if response.stop_reason == "max_tokens":
        if json_schema or thinking:
            # JSON обрізаний = зламаний; текст, обрізаний через довгі міркування, —
            # краще повторити швидко без них, ніж віддати пів документа.
            raise LLMError(
                "Відповідь вийшла надто довгою і не вмістилась у ліміт. "
                "Спробуйте розбити питання на кілька вужчих.",
                status_code=502,
                retry_fast=True,
            )
        usage["truncated"] = True
        text += "\n\n*(Відповідь обрізана через ліміт довжини.)*"

    if not text.strip():
        raise LLMError(
            "Модель повернула порожню відповідь — спробуйте ще раз.", status_code=502, retry_fast=True
        )

    if json_schema:
        try:
            return json.loads(text), usage
        except json.JSONDecodeError as e:
            raise LLMError(
                "Не вдалося розібрати відповідь моделі — спробуйте ще раз.", retry_fast=True
            ) from e

    return text, usage
