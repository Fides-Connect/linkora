"""
AI Conversation Service
Manages the lifecycle of one AI conversation session in Firestore.
"""
import logging
from typing import Optional

from ..firestore_service import FirestoreService
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

    def __init__(self, firestore_service: FirestoreService | None) -> None:
        self._firestore = firestore_service
        self._conversation_id: Optional[str] = None
        self._user_id: Optional[str] = None
        self._sequence: int = 0
        self._request_id: Optional[str] = None

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
        """Update the topic title on the conversation document.

        A5: Truncated gracefully at the nearest word boundary before 300 characters
        so no multi-byte character or word is split.
        """
        if self._conversation_id is None:
            return
        if self._firestore is None:
            return
        try:
            # Graceful word-boundary truncation at 300 characters (A5)
            if len(title) > 300:
                truncated = title[:301].rsplit(None, 1)[0]  # split at last space within 301 chars
                if not truncated or len(truncated) > 300:
                    # Fallback: encode/decode to ensure we don't split a multi-byte char
                    encoded = title.encode("utf-8")[:300]
                    truncated = encoded.decode("utf-8", errors="ignore")
            else:
                truncated = title
            await self._firestore.update_ai_conversation(
                self._user_id, self._conversation_id, {"topic_title": truncated}
            )
        except Exception as exc:
            logger.error("AIConversationService.set_topic_title error: %s", exc, exc_info=True)

    async def set_request_id(self, request_id: str) -> None:
        """Link a service request ID to this conversation."""
        if self._conversation_id is None:
            return
        self._request_id = request_id  # cache in memory for get_request_id()
        if self._firestore is None:
            return
        try:
            await self._firestore.update_ai_conversation(
                self._user_id, self._conversation_id, {"request_id": request_id}
            )
        except Exception as exc:
            logger.error("AIConversationService.set_request_id error: %s", exc, exc_info=True)

    async def get_request_id(self) -> Optional[str]:
        """Return the service request ID linked to this conversation (in-memory cache)."""
        return self._request_id

    async def close_session(self, final_stage: ConversationStage, request_summary: str = "") -> None:
        """Mark the conversation as closed with the final stage and optional request summary."""
        if self._conversation_id is None:
            return
        if self._firestore is None:
            return
        try:
            update: dict = {"final_stage": final_stage.value}
            if request_summary:
                update["request_summary"] = request_summary
            await self._firestore.update_ai_conversation(
                self._user_id,
                self._conversation_id,
                update,
            )
        except Exception as exc:
            logger.error("AIConversationService.close_session error: %s", exc, exc_info=True)

    async def get_recent_session_summary(self, user_id: str) -> Optional[dict]:
        """Return a summary dict of the most recent session if within 24 hours, else None.

        Returns dict with keys: final_stage, topic_title, request_summary, ended_at.
        Returns None when firestore_service is None or no recent session exists.
        """
        if self._firestore is None:
            return None
        try:
            recent = await self._firestore.get_recent_ai_conversation(user_id)
            if not recent:
                return None
            final_stage_str = recent.get("final_stage")
            if not final_stage_str:
                return None
            try:
                final_stage = ConversationStage(final_stage_str)
            except ValueError:
                return None
            return {
                "final_stage": final_stage,
                "topic_title": recent.get("topic_title", ""),
                "request_summary": recent.get("request_summary", ""),
                "ended_at": recent.get("last_message_at"),
            }
        except Exception as exc:
            logger.error("AIConversationService.get_recent_session_summary error: %s", exc, exc_info=True)
            return None
