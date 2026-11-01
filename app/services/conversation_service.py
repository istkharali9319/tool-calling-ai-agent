"""Stores conversations so the assistant can use earlier turns as context."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.models import Conversation, Message


class ConversationNotFoundError(Exception):
    def __init__(self, conversation_id: str) -> None:
        super().__init__(f"Conversation {conversation_id} not found.")
        self.conversation_id = conversation_id


class ConversationService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, conversation_id: str) -> Conversation:
        conversation = self._db.get(Conversation, conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)
        return conversation

    def get_or_create(self, conversation_id: str | None) -> Conversation:
        """Return the existing conversation, or a new unsaved one when no ID is given."""
        if conversation_id:
            return self.get(conversation_id)
        conversation = Conversation()
        self._db.add(conversation)
        self._db.flush()
        return conversation

    def history(self, conversation: Conversation, limit: int) -> list[dict[str, str]]:
        """The last `limit` messages, oldest first, in Responses API input format."""
        if limit <= 0:
            return []
        rows = self._db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.id.desc())
            .limit(limit)
        ).all()
        return [{"role": m.role, "content": m.content} for m in reversed(rows)]

    def record_turn(
        self,
        conversation: Conversation,
        user_message: str,
        assistant_message: str,
        tool_calls: list[dict[str, Any]],
    ) -> None:
        """Save the user message and the reply together, so a failed request leaves no half turn."""
        self._db.add_all(
            [
                Message(conversation_id=conversation.id, role="user", content=user_message),
                Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=assistant_message,
                    tool_calls=tool_calls or None,
                ),
            ]
        )
        conversation.updated_at = datetime.now(timezone.utc)
        self._db.commit()

    def list_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        """Most recently updated conversations, with a title taken from the first user message."""
        conversations = self._db.scalars(
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
        ).all()
        summaries = []
        for conversation in conversations:
            first_user = next((m.content for m in conversation.messages if m.role == "user"), "")
            title = " ".join(first_user.split())
            summaries.append(
                {
                    "conversation_id": conversation.id,
                    "title": (title[:60] + "…") if len(title) > 60 else (title or "New conversation"),
                    "message_count": len(conversation.messages),
                    "updated_at": conversation.updated_at,
                }
            )
        return summaries

    def messages(self, conversation_id: str) -> list[Message]:
        return list(self.get(conversation_id).messages)

    def delete(self, conversation_id: str) -> None:
        self._db.delete(self.get(conversation_id))
        self._db.commit()
