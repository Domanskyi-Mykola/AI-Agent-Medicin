"""POST /api/chat — клінічний Q&A на основі бази знань (RAG-grounded)."""
from fastapi import APIRouter, Depends, HTTPException

from app.audit import log_llm_call
from app.auth import get_current_user
from app.config import get_settings
from app.llm.claude import LLMError, LLMNotConfigured, ask_claude
from app.prompts import (
    CHAT_SYSTEM_PROMPT,
    DISCLAIMER,
    NO_DATA_ANSWER,
    build_chat_user_prompt,
)
from app.rag.retriever import retrieve
from app.schemas import ChatRequest, ChatResponse, Citation

router = APIRouter()


@router.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest, user: dict = Depends(get_current_user)) -> ChatResponse:
    # НАГАДУВАННЯ (безпека): питання лікаря не повинно містити даних, що
    # ідентифікують пацієнта — UI попереджає про це, а бекенд нічого,
    # крім тексту питання, не зберігає (див. app/audit.py).
    chunks = retrieve(req.question)

    if not chunks:
        # RAG-grounded: без релевантних чанків LLM не викликається взагалі —
        # чесно кажемо, що даних немає, замість вільної генерації.
        log_llm_call(
            "chat",
            {
                "user": user["id"],
                "question": req.question,
                "retrieved_chunks": [],
                "answer": NO_DATA_ANSWER,
                "llm_called": False,
            },
        )
        return ChatResponse(answer=NO_DATA_ANSWER, citations=[], disclaimer=DISCLAIMER)

    try:
        answer, usage = ask_claude(
            user=build_chat_user_prompt(req.question, chunks),
            system=CHAT_SYSTEM_PROMPT,
            max_tokens=get_settings().max_answer_tokens,
        )
    except LLMNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))
    except LLMError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))

    # Одна цитата на чанк, у тому ж порядку: citations[N-1] відповідає
    # посиланню [N] у тексті відповіді.
    citations = [
        Citation(
            source=c.metadata.get("source_name", "невідоме джерело"),
            document_number=c.metadata.get("document_number"),
            date=c.metadata.get("date"),
            section=c.metadata.get("section"),
        )
        for c in chunks
    ]

    log_llm_call(
        "chat",
        {
            "user": user["id"],
            "question": req.question,
            "retrieved_chunks": [
                {"id": c.id, "distance": c.distance} for c in chunks
            ],
            "answer": answer,
            "llm_called": True,
            "usage": usage,
        },
    )

    return ChatResponse(answer=answer, citations=citations, disclaimer=DISCLAIMER)
