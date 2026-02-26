"""
AI Conversation Service
Manages the lifecycle of one AI conversation session in Firestore.
"""
import logging
from typing import Optional

from .conversation_service import ConversationStage

logger = logging.getLogger(__name__)


class AIConversationService:
    """
    Manages the lifecycle of a single AI conversation session.

    Thin wrapper over FirestoreService that:
    - Creates a conversation document under users/{user_id}/ai_conversations on open_session
    - Saves user/assistant messages with auto-incrementing sequence numbers
    - Updates topic_title, request_id, and final_stage as the conversation progresses
    - Is safe to use with firestore_service=None (all methods become no-ops)
    """

    def __init__(self, firestore_service) -> None:
        self._firestore = firestore_service
        self._conversation_id: Optional[str] = None
        self._user_id: Optional[str] = None
        self._sequence: int = 0

    @property
    def conversation_id(self) -> Optional[str]:
        return self._conversation_id

    async def open_session(
        self,
        user_id: str,
        session_id: str = "",
        topic_title: str = "",
    ) -> None:
        """Create a conversation document under users/{user_id}/ai_conversations (idempotent)."""
        if self._conversation_id is not None:
            return
        if self._firestore is None:
            return
        try:
            self._user_id = user_id
            data = {
                "user_id": user_id,
                "topic_title": topic_title,
            }
            self._conversation_id = await self._firestore.create_ai_conversation(user_id, data)
        except Exception as exc:
            logger.error("AIConversationService.open_session error: %s", exc, exc_info=True)

    async def save_message(
        self,
        role: str,
        text: str,
        stage: ConversationStage,
    ) -> None:
        """Persist a message to the conversation's messages subcollection."""
        if self._conversation_id is None:
            return
        if self._firestore is None:
            return
        try:
            sequence = self._sequence
            self._sequence += 1
            await self._firestore.create_ai_conversation_message(
                self._user_id, self._conversation_id, role, text, stage, sequence
            )
        except Exception as exc:
            logger.error("AIConversationService.save_message error: %s", exc, exc_info=True)

    async def set_topic_title(self, title: str) -> None:
        """Update the topic title on the conversation document."""
        if self._conversation_id is None:
            return
        if self._firestore is None:
            return
        try:
            await self._firestore.update_ai_conversation(
                self._user_id, self._conversation_id, {"topic_title": title}
            )
        except Exception as exc:
            logger.error("AIConversationService.set_topic_title error: %s", exc, exc_info=True)

    async def set_request_id(self, request_id: str) -> None:
        """Link a service request ID to this conversation."""
        if self._conversation_id is None:
            return
        if self._firestore is None:
            return
        try:
            await self._firestore.update_ai_conversation(
                self._user_id, self._conversation_id, {"request_id": request_id}
            )
        except Exception as exc:
            logger.error("AIConversationService.set_request_id error: %s", exc, exc_info=True)

    async def close_session(self, final_stage: ConversationStage) -> None:
        """Mark the conversation as closed with the final stage."""
        if self._conversation_id is None:
            return
        if self._firestore is None:
            return
        try:
            await self._firestore.update_ai_conversation(
                self._user_id,
                self._conversation_id,
                {"final_stage": final_stage.value},
            )
        except Exception as exc:
            logger.error("AIConversationService.close_session error: %s", exc, exc_info=True)
