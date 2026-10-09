"""AI 助手对话的请求/响应模型。"""

from pydantic import BaseModel, Field

from app.schemas.search import SearchResultOut


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    reply: str
    hits: list[SearchResultOut]
