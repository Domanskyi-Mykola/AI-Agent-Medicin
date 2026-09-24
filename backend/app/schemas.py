"""Pydantic-схеми запитів і відповідей API."""
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)


class Citation(BaseModel):
    """Джерело, на яке є посилання [n] у kb_answer (n — номер фрагмента в промпті)."""

    n: int
    source: str
    document_number: Optional[str] = None
    date: Optional[str] = None
    section: Optional[str] = None


Coverage = Literal["full", "partial", "none"]


class ChatResponse(BaseModel):
    # Частина відповіді, що спирається на базу знань, з посиланнями [n].
    kb_answer: str
    # Доповнення із загальних клінічних знань моделі (лише в режимі hybrid) —
    # фронтенд показує його окремим, явно позначеним блоком, без цитат.
    general_answer: str
    kb_coverage: Coverage
    out_of_scope: bool
    answer_mode: Literal["hybrid", "strict"]
    citations: list[Citation]
    disclaimer: str
    # Уся відповідь одним markdown-текстом (для логів і сумісності).
    answer: str


DocType = Literal["discharge_summary", "case_history_section", "dissertation_section"]


class DocumentRequest(BaseModel):
    # УВАГА (безпека): жодне з цих полів не повинно містити даних, що
    # ідентифікують пацієнта — вони йдуть до AI. ПІБ, дати, № картки фронтенд
    # підставляє локально через токени {{...}} (див. prompts.PASSPORT_*).
    doc_type: DocType
    diagnosis: str = Field(..., min_length=3, max_length=2000)
    procedure: str = Field("", max_length=4000)
    notes: str = Field("", max_length=8000)
    complaints: str = Field("", max_length=4000)
    anamnesis: str = Field("", max_length=4000)
    examination: str = Field("", max_length=4000)
    investigations: str = Field("", max_length=4000)
    discharge_status: str = Field("", max_length=4000)
    recommendations: str = Field("", max_length=4000)
    # Дозволити моделі запропонувати типові (загальноприйняті) рекомендації
    # для цього діагнозу/втручання — з явною позначкою «типова, перевірте».
    typical_recommendations: bool = True


class DocumentResponse(BaseModel):
    text: str
    disclaimer: str
