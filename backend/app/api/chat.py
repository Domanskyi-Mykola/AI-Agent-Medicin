"""POST /api/chat — клінічний Q&A: відповідь з бази знань (з цитатами) +,
у режимі hybrid, явно позначене доповнення із загальних клінічних знань."""
import re

from fastapi import APIRouter, Depends, HTTPException

from app.audit import log_llm_call
from app.auth import get_current_user
from app.config import get_settings
from app.llm.claude import LLMError, LLMNotConfigured, ask_claude
from app.prompts import (
    CHAT_SCHEMA,
    DISCLAIMER,
    NO_DATA_ANSWER,
    OUT_OF_SCOPE_ANSWER,
    build_chat_user_prompt,
    chat_system_prompt,
)
from app.rag.retriever import group_by_section, retrieve
from app.schemas import ChatRequest, ChatResponse, Citation

router = APIRouter()

_CITE_RE = re.compile(r"\[(\d{1,3}(?:\s*,\s*\d{1,3})*)\]")

GENERAL_HEADER = "Загальні клінічні знання (не з бази знань — перевірте за чинними протоколами)"


def _renumber_citations(text: str, n_fragments: int) -> tuple[str, list[int]]:
    """Перенумеровує посилання підряд у порядку першої появи: [4]…[9]…[4] -> [1]…[2]…[1].

    Повертає новий текст і список старих номерів фрагментів (індекс + 1 = новий
    номер). «[2, 5]» перетворюється на «[1][2]». Номери поза межами фрагментів
    лишаються як є і в джерела не потрапляють.
    """
    order: list[int] = []
    for group in _CITE_RE.findall(text):
        for part in group.split(","):
            n = int(part.strip())
            if 1 <= n <= n_fragments and n not in order:
                order.append(n)
    new_of = {old: new for new, old in enumerate(order, start=1)}

    def sub(m: re.Match) -> str:
        nums = [new_of[int(p)] for p in m.group(1).split(",") if int(p) in new_of]
        return "".join(f"[{n}]" for n in dict.fromkeys(nums)) if nums else m.group(0)

    return _CITE_RE.sub(sub, text), order


def _combined(kb: str, general: str) -> str:
    parts = [p for p in (kb.strip(),) if p]
    if general.strip():
        parts.append(f"**{GENERAL_HEADER}:**\n\n{general.strip()}")
    return "\n\n".join(parts)


@router.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest, user: dict = Depends(get_current_user)) -> ChatResponse:
    # НАГАДУВАННЯ (безпека): питання лікаря не повинно містити даних, що
    # ідентифікують пацієнта — UI попереджає про це, а бекенд нічого,
    # крім тексту питання, не зберігає (див. app/audit.py).
    s = get_settings()
    mode = "strict" if s.answer_mode == "strict" else "hybrid"
    chunks = retrieve(req.question)
    fragments = group_by_section(chunks)

    def respond(kb: str, general: str, coverage: str, out_of_scope: bool, citations: list[Citation]):
        return ChatResponse(
            kb_answer=kb,
            general_answer=general,
            kb_coverage=coverage,
            out_of_scope=out_of_scope,
            answer_mode=mode,
            citations=citations,
            disclaimer=DISCLAIMER,
            answer=_combined(kb, general),
        )

    if mode == "strict" and not chunks:
        # Строгий режим: без релевантних фрагментів LLM не викликається взагалі.
        log_llm_call("chat", {
            "user": user["id"], "question": req.question, "mode": mode,
            "retrieved_chunks": [], "answer": NO_DATA_ANSWER, "llm_called": False,
        })
        return respond(NO_DATA_ANSWER, "", "none", False, [])

    try:
        result, usage = ask_claude(
            user=build_chat_user_prompt(req.question, fragments),
            system=chat_system_prompt(mode),
            max_tokens=s.max_answer_tokens,
            json_schema=CHAT_SCHEMA,
            effort=s.claude_effort,
        )
    except LLMNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))
    except LLMError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))

    out_of_scope = bool(result.get("out_of_scope"))
    kb = (result.get("kb_answer") or "").strip()
    general = (result.get("general_answer") or "").strip() if mode == "hybrid" else ""
    coverage = result.get("kb_coverage") or "none"

    if out_of_scope:
        kb, general, coverage = OUT_OF_SCOPE_ANSWER, "", "none"
        citations: list[Citation] = []
    else:
        kb, cited = _renumber_citations(kb, len(fragments))
        citations = [
            Citation(
                n=new_n,
                source=fragments[old - 1].metadata.get("source_name", "невідоме джерело"),
                document_number=fragments[old - 1].metadata.get("document_number"),
                date=fragments[old - 1].metadata.get("date"),
                section=fragments[old - 1].metadata.get("section"),
            )
            for new_n, old in enumerate(cited, start=1)
        ]
        if not cited and mode == "hybrid" and kb:
            # kb_answer без жодного посилання не вважаємо відповіддю «з бази» —
            # показуємо його разом із загальними знаннями, під їх позначкою.
            general = "\n\n".join(p for p in (kb, general) if p)
            kb, coverage = "", "none"
        if not kb and not general:
            kb, coverage = NO_DATA_ANSWER, "none"

    log_llm_call("chat", {
        "user": user["id"],
        "question": req.question,
        "mode": mode,
        "retrieved_chunks": [{"id": c.id, "distance": c.distance} for c in chunks],
        "cited_fragments": [fragments[old - 1].id for old in cited] if not out_of_scope else [],
        "kb_coverage": coverage,
        "out_of_scope": out_of_scope,
        "kb_answer": kb,
        "general_answer": general,
        "llm_called": True,
        "usage": usage,
    })

    return respond(kb, general, coverage, out_of_scope, citations)
