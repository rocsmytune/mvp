from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.local import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse
from app.services import chatbot

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(
    data: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """AI 助手对话（只读，所有登录用户可用，可问全库）。"""
    return chatbot.chat(db, user, data.message)
