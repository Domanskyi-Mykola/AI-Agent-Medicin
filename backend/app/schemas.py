"""Pydantic-схеми запитів і відповідей API."""
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)


class Citation(BaseModel):
    """Одне джерело. Індекс у списку (починаючи з 1) відповідає посиланням [N] у відповіді."""

    source: str
    document_number: Optional[str] = None
    date: Optional[str] = None
    section: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    disclaimer: str


DocType = Literal["discharge_summary", "case_history_section", "dissertation_section"]


class DocumentRequest(BaseModel):
    doc_type: DocType
    diagnosis: str = Field(..., min_length=3, max_length=2000)
    procedure: str = Field("", max_length=2000)
    notes: str = Field("", max_length=8000)


class DocumentResponse(BaseModel):
    text: str
    disclaimer: str
