"""POST /api/documents/generate — чернетки медичної документації."""
from fastapi import APIRouter, Depends, HTTPException

from app.audit import log_llm_call
from app.auth import get_current_user
from app.config import get_settings
from app.llm.claude import LLMError, LLMNotConfigured, ask_claude
from app.prompts import DOC_DISCLAIMER, DOC_SYSTEM_PROMPT, build_document_user_prompt
from app.schemas import DocumentRequest, DocumentResponse

router = APIRouter()


@router.post("/api/documents/generate", response_model=DocumentResponse)
def generate_document(
    req: DocumentRequest, user: dict = Depends(get_current_user)
) -> DocumentResponse:
    # НАГАДУВАННЯ (безпека): ввід лікаря не повинен містити даних, що
    # ідентифікують пацієнта (ПІБ, дата народження, № карти). UI попереджає
    # про це; ідентифікуючі поля фронтенд підставляє локально через токени {{...}}.
    s = get_settings()
    try:
        text, usage = ask_claude(
            user=build_document_user_prompt(req),
            system=DOC_SYSTEM_PROMPT,
            max_tokens=s.max_document_tokens,
            effort=s.claude_effort,
        )
    except LLMNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))
    except LLMError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))

    log_llm_call(
        "documents",
        {
            "user": user["id"],
            "doc_type": req.doc_type,
            "input": req.model_dump(exclude={"doc_type"}),
            "answer": text,
            "llm_called": True,
            "usage": usage,
        },
    )

    return DocumentResponse(text=text, disclaimer=DOC_DISCLAIMER)
