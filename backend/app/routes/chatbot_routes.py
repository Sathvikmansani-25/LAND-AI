import sys

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import auth
from app import chatbot as rule_chatbot
from app.config import settings
from app.database import get_db, now_iso
from app.models import ChatLog, User
from app.schemas import ChatRequest

router = APIRouter(prefix="/api/chatbot", tags=["chatbot"])


@router.post("")
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    result = None
    used_llm = False
    if settings.llm_chatbot_enabled and settings.groq_api_key:
        try:
            from app import llm_chatbot  # imported lazily so a missing key never affects startup

            result = llm_chatbot.answer(db, payload.message)
            used_llm = True
        except Exception as e:  # noqa: BLE001 -- any LLM/network failure falls back to the offline bot
            print(f"[chatbot] LLM backend failed, falling back to rule-based bot: {e}", file=sys.stderr)

    if result is None:
        result = rule_chatbot.answer(db, payload.message)

    db.add(
        ChatLog(
            username=current_user.username,
            message=payload.message,
            response=result["response"],
            created_at=now_iso(),
        )
    )
    db.commit()

    result = dict(result)
    result["engine"] = "llm" if used_llm else "rule_based"
    return result
