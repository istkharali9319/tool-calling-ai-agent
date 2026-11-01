from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

MessageText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)]


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: MessageText = Field(examples=["What is 1250 multiplied by 12?"])
    conversation_id: UUID | None = Field(
        default=None, description="Continue an existing conversation. Omit to start a new one."
    )


class ToolCallInfo(BaseModel):
    name: str
    ok: bool
    arguments: dict[str, Any]
    result: Any | None = None
    error: str | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    model: str
    tool_calls: list[ToolCallInfo]


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    tool_calls: list[ToolCallInfo] | None = None
    created_at: datetime


class ConversationOut(BaseModel):
    conversation_id: str
    messages: list[MessageOut]


class ConversationSummary(BaseModel):
    conversation_id: str
    title: str
    message_count: int
    updated_at: datetime


class ToolInfo(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]
