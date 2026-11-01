from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database.connection import get_db
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationOut,
    ConversationSummary,
    MessageOut,
    ToolCallInfo,
    ToolInfo,
)
from app.services.conversation_service import ConversationService
from app.services.openai_service import OpenAIService, get_openai_service
from app.services.tool_executor import ToolExecutor

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    ai: OpenAIService = Depends(get_openai_service),
    settings: Settings = Depends(get_settings),
) -> ChatResponse:
    """Send a message to the assistant. The backend runs any tools the model asks for."""
    conversations = ConversationService(db)
    conversation_id = str(payload.conversation_id) if payload.conversation_id else None
    conversation = conversations.get_or_create(conversation_id)
    history = conversations.history(conversation, settings.history_limit)

    try:
        reply = ai.generate_reply(db, history, payload.message)
    except Exception:
        db.rollback()
        raise

    tool_calls = [result.to_dict() for result in reply.tool_calls]
    conversations.record_turn(conversation, payload.message, reply.text, tool_calls)

    return ChatResponse(
        conversation_id=conversation.id,
        reply=reply.text,
        model=reply.model,
        tool_calls=[ToolCallInfo(**call) for call in tool_calls],
    )


@router.get("/conversations", response_model=list[ConversationSummary])
def list_conversations(
    limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)
) -> list[ConversationSummary]:
    return [ConversationSummary(**c) for c in ConversationService(db).list_recent(limit)]


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
def get_conversation(conversation_id: str, db: Session = Depends(get_db)) -> ConversationOut:
    messages = ConversationService(db).messages(conversation_id)
    return ConversationOut(
        conversation_id=conversation_id,
        messages=[MessageOut.model_validate(m) for m in messages],
    )


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: str, db: Session = Depends(get_db)) -> Response:
    ConversationService(db).delete(conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tools", response_model=list[ToolInfo])
def list_tools() -> list[ToolInfo]:
    """The tools the assistant may request. Only these can ever be executed."""
    return [
        ToolInfo(name=d["name"], description=d["description"], parameters=d["parameters"])
        for d in ToolExecutor().definitions()
    ]
