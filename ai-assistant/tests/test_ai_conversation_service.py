"""
Tests for AIConversationService — manages lifecycle of one AI conversation session.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, Mock

from ai_assistant.services.ai_conversation_service import AIConversationService
from ai_assistant.services.conversation_service import ConversationStage


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_fs(conv_id="conv_abc"):
    """Return a mock FirestoreService with the AI-conversation methods wired."""
    fs = Mock()
    fs.create_ai_conversation = AsyncMock(return_value=conv_id)
    fs.create_ai_conversation_message = AsyncMock(return_value="msg_1")
    fs.update_ai_conversation = AsyncMock(return_value=True)
    fs.get_ai_conversations = AsyncMock(return_value=[])
    fs.get_ai_conversation_messages = AsyncMock(return_value=[])
    return fs


# ─────────────────────────────────────────────────────────────────────────────
# open_session
# ─────────────────────────────────────────────────────────────────────────────

class TestOpenSession:

    async def test_open_session_creates_conversation(self):
        fs = _make_fs("conv_abc")
        svc = AIConversationService(firestore_service=fs)
        await svc.open_session(user_id="u1", session_id="s1")
        fs.create_ai_conversation.assert_called_once()
        assert svc.conversation_id == "conv_abc"

    async def test_open_session_is_idempotent(self):
        """Second call must be a no-op — firestore called only once."""
        fs = _make_fs("conv_abc")
        svc = AIConversationService(firestore_service=fs)
        await svc.open_session(user_id="u1", session_id="s1")
        await svc.open_session(user_id="u1", session_id="s1")
        assert fs.create_ai_conversation.call_count == 1

    async def test_open_session_passes_user_id(self):
        fs = _make_fs("conv_xyz")
        svc = AIConversationService(firestore_service=fs)
        await svc.open_session(user_id="user_99", session_id="sess_99")
        # create_ai_conversation(user_id, data) — first arg is the user_id string
        assert fs.create_ai_conversation.call_args[0][0] == "user_99"
        # data dict contains user_id for denormalization but no session_id
        call_data = fs.create_ai_conversation.call_args[0][1]
        assert call_data["user_id"] == "user_99"
        assert "session_id" not in call_data

    async def test_open_session_passes_topic_title_when_provided(self):
        fs = _make_fs("conv_abc")
        svc = AIConversationService(firestore_service=fs)
        await svc.open_session(user_id="u1", session_id="s1", topic_title="Test topic")
        call_data = fs.create_ai_conversation.call_args[0][1]
        assert call_data.get("topic_title") == "Test topic"

    async def test_open_session_default_topic_title_is_empty(self):
        fs = _make_fs("conv_abc")
        svc = AIConversationService(firestore_service=fs)
        await svc.open_session(user_id="u1", session_id="s1")
        call_data = fs.create_ai_conversation.call_args[0][1]
        assert call_data.get("topic_title") == ""


# ─────────────────────────────────────────────────────────────────────────────
# save_message
# ─────────────────────────────────────────────────────────────────────────────

class TestSaveMessage:

    async def test_save_message_before_open_session_is_noop(self):
        """save_message before open_session must not raise and must not call firestore."""
        fs = _make_fs()
        svc = AIConversationService(firestore_service=fs)
        await svc.save_message(role="user", text="hello", stage=ConversationStage.TRIAGE)
        fs.create_ai_conversation_message.assert_not_called()

    async def test_save_message_calls_firestore(self):
        fs = _make_fs("conv_1")
        svc = AIConversationService(firestore_service=fs)
        await svc.open_session(user_id="u1", session_id="s1")
        await svc.save_message(role="user", text="hello", stage=ConversationStage.TRIAGE)
        fs.create_ai_conversation_message.assert_called_once_with(
            "u1", "conv_1", "user", "hello", ConversationStage.TRIAGE, 0
        )

    async def test_save_message_increments_sequence(self):
        fs = _make_fs("conv_1")
        svc = AIConversationService(firestore_service=fs)
        await svc.open_session(user_id="u1", session_id="s1")
        await svc.save_message(role="user", text="a", stage=ConversationStage.TRIAGE)
        await svc.save_message(role="assistant", text="b", stage=ConversationStage.TRIAGE)
        await svc.save_message(role="user", text="c", stage=ConversationStage.FINALIZE)
        calls = fs.create_ai_conversation_message.call_args_list
        assert calls[0][0][5] == 0
        assert calls[1][0][5] == 1
        assert calls[2][0][5] == 2

    async def test_save_message_passes_role_and_text(self):
        fs = _make_fs("conv_1")
        svc = AIConversationService(firestore_service=fs)
        await svc.open_session(user_id="u1", session_id="s1")
        await svc.save_message(role="assistant", text="Hallo!", stage=ConversationStage.TRIAGE)
        call_args = fs.create_ai_conversation_message.call_args[0]
        assert call_args[2] == "assistant"
        assert call_args[3] == "Hallo!"
        assert call_args[4] == ConversationStage.TRIAGE


# ─────────────────────────────────────────────────────────────────────────────
# set_topic_title
# ─────────────────────────────────────────────────────────────────────────────

class TestSetTopicTitle:

    async def test_set_topic_title_calls_firestore(self):
        fs = _make_fs("conv_1")
        svc = AIConversationService(firestore_service=fs)
        await svc.open_session(user_id="u1", session_id="s1")
        await svc.set_topic_title("find electrician")
        fs.update_ai_conversation.assert_called_once()
        args = fs.update_ai_conversation.call_args[0]
        assert args[0] == "u1"       # user_id
        assert args[1] == "conv_1"   # conversation_id
        assert args[2].get("topic_title") == "find electrician"

    async def test_set_topic_title_before_open_session_is_noop(self):
        fs = _make_fs()
        svc = AIConversationService(firestore_service=fs)
        await svc.set_topic_title("something")
        fs.update_ai_conversation.assert_not_called()

    async def test_set_topic_title_truncates_to_300_chars(self):
        """Titles longer than 300 chars must be truncated before Firestore write."""
        fs = _make_fs("conv_2")
        svc = AIConversationService(firestore_service=fs)
        await svc.open_session(user_id="u1", session_id="s1")
        long_title = "x" * 400
        await svc.set_topic_title(long_title)
        args = fs.update_ai_conversation.call_args[0]
        stored = args[2].get("topic_title", "")
        assert len(stored) == 300
        assert stored == "x" * 300


# ─────────────────────────────────────────────────────────────────────────────
# close_session
# ─────────────────────────────────────────────────────────────────────────────

class TestCloseSession:

    async def test_close_session_calls_update_with_final_stage(self):
        fs = _make_fs("conv_1")
        svc = AIConversationService(firestore_service=fs)
        await svc.open_session(user_id="u1", session_id="s1")
        await svc.close_session(final_stage=ConversationStage.COMPLETED)
        fs.update_ai_conversation.assert_called_once()
        call_data = fs.update_ai_conversation.call_args[0][2]
        assert call_data.get("final_stage") == ConversationStage.COMPLETED.value

    async def test_close_session_before_open_is_noop(self):
        fs = _make_fs()
        svc = AIConversationService(firestore_service=fs)
        await svc.close_session(final_stage=ConversationStage.TRIAGE)
        fs.update_ai_conversation.assert_not_called()

    async def test_close_session_uses_conversation_id(self):
        fs = _make_fs("conv_close_test")
        svc = AIConversationService(firestore_service=fs)
        await svc.open_session(user_id="u1", session_id="s1")
        await svc.close_session(final_stage=ConversationStage.FINALIZE)
        args = fs.update_ai_conversation.call_args[0]
        assert args[0] == "u1"              # user_id
        assert args[1] == "conv_close_test" # conversation_id


# ─────────────────────────────────────────────────────────────────────────────
# set_request_id
# ─────────────────────────────────────────────────────────────────────────────

class TestSetRequestId:

    async def test_set_request_id_calls_firestore(self):
        fs = _make_fs("conv_1")
        svc = AIConversationService(firestore_service=fs)
        await svc.open_session(user_id="u1", session_id="s1")
        await svc.set_request_id("req_abc123")
        fs.update_ai_conversation.assert_called_once()
        args = fs.update_ai_conversation.call_args[0]
        assert args[0] == "u1"          # user_id
        assert args[1] == "conv_1"      # conversation_id
        assert args[2].get("request_id") == "req_abc123"

    async def test_set_request_id_before_open_session_is_noop(self):
        fs = _make_fs()
        svc = AIConversationService(firestore_service=fs)
        await svc.set_request_id("req_abc")
        fs.update_ai_conversation.assert_not_called()

    async def test_set_request_id_null_firestore_no_raise(self):
        svc = AIConversationService(firestore_service=None)
        await svc.set_request_id("req_abc")


# ─────────────────────────────────────────────────────────────────────────────
# null firestore — all methods must be no-ops
# ─────────────────────────────────────────────────────────────────────────────

class TestNullFirestore:
    """All methods must be safe no-ops when firestore_service=None."""

    async def test_open_session_no_raise(self):
        svc = AIConversationService(firestore_service=None)
        await svc.open_session(user_id="u1", session_id="s1")
        assert svc.conversation_id is None

    async def test_save_message_no_raise(self):
        svc = AIConversationService(firestore_service=None)
        await svc.open_session(user_id="u1", session_id="s1")
        await svc.save_message(role="user", text="hello", stage=ConversationStage.TRIAGE)

    async def test_set_topic_title_no_raise(self):
        svc = AIConversationService(firestore_service=None)
        await svc.set_topic_title("anything")

    async def test_close_session_no_raise(self):
        svc = AIConversationService(firestore_service=None)
        await svc.close_session(final_stage=ConversationStage.TRIAGE)

    async def test_conversation_id_is_none(self):
        svc = AIConversationService(firestore_service=None)
        assert svc.conversation_id is None


# ─────────────────────────────────────────────────────────────────────────────
# close_session — request_summary (GAP-2)
# ─────────────────────────────────────────────────────────────────────────────

class TestCloseSessionRequestSummary:

    async def test_close_session_persists_request_summary(self):
        fs = _make_fs("conv_1")
        svc = AIConversationService(firestore_service=fs)
        await svc.open_session(user_id="u1", session_id="s1")
        await svc.close_session(
            final_stage=ConversationStage.COMPLETED,
            request_summary="User booked a plumber for Tuesday.",
        )
        call_data = fs.update_ai_conversation.call_args[0][2]
        assert call_data.get("request_summary") == "User booked a plumber for Tuesday."

    async def test_close_session_empty_summary_not_included(self):
        """An empty request_summary must not be written to Firestore."""
        fs = _make_fs("conv_1")
        svc = AIConversationService(firestore_service=fs)
        await svc.open_session(user_id="u1", session_id="s1")
        await svc.close_session(final_stage=ConversationStage.COMPLETED, request_summary="")
        call_data = fs.update_ai_conversation.call_args[0][2]
        assert "request_summary" not in call_data

    async def test_close_session_default_empty_summary_not_included(self):
        """Default call (no request_summary) must not include the field."""
        fs = _make_fs("conv_1")
        svc = AIConversationService(firestore_service=fs)
        await svc.open_session(user_id="u1", session_id="s1")
        await svc.close_session(final_stage=ConversationStage.TRIAGE)
        call_data = fs.update_ai_conversation.call_args[0][2]
        assert "request_summary" not in call_data


# ─────────────────────────────────────────────────────────────────────────────
# get_recent_session_summary (GAP-2)
# ─────────────────────────────────────────────────────────────────────────────

class TestGetRecentSessionSummary:

    def _make_recent_conv(self, minutes_ago=10, final_stage=None, topic_title="Test topic", request_summary=""):
        last_message_at = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        return {
            "user_id": "u1",
            "topic_title": topic_title,
            "request_summary": request_summary,
            "final_stage": (final_stage or ConversationStage.TRIAGE).value,
            "last_message_at": last_message_at,
            "ended_at": last_message_at,
        }

    async def test_returns_summary_for_recent_conversation(self):
        fs = _make_fs()
        fs.get_recent_ai_conversation = AsyncMock(return_value=
            self._make_recent_conv(minutes_ago=30, final_stage=ConversationStage.TRIAGE)
        )
        svc = AIConversationService(firestore_service=fs)
        result = await svc.get_recent_session_summary("u1")
        assert result is not None
        assert result["final_stage"] == ConversationStage.TRIAGE
        assert result["topic_title"] == "Test topic"

    async def test_returns_none_when_no_conversations(self):
        fs = _make_fs()
        fs.get_recent_ai_conversation = AsyncMock(return_value=None)
        svc = AIConversationService(firestore_service=fs)
        result = await svc.get_recent_session_summary("u1")
        assert result is None

    async def test_returns_none_when_outside_24h_window(self):
        """get_recent_ai_conversation already filters by time; returns None when stale."""
        fs = _make_fs()
        fs.get_recent_ai_conversation = AsyncMock(return_value=None)
        svc = AIConversationService(firestore_service=fs)
        result = await svc.get_recent_session_summary("u1")
        assert result is None

    async def test_returns_none_when_no_firestore(self):
        svc = AIConversationService(firestore_service=None)
        result = await svc.get_recent_session_summary("u1")
        assert result is None

    async def test_includes_request_summary_in_result(self):
        fs = _make_fs()
        fs.get_recent_ai_conversation = AsyncMock(return_value=
            self._make_recent_conv(
                minutes_ago=10,
                request_summary="User needs a plumber urgently.",
            )
        )
        svc = AIConversationService(firestore_service=fs)
        result = await svc.get_recent_session_summary("u1")
        assert result["request_summary"] == "User needs a plumber urgently."

    async def test_calls_get_recent_ai_conversation_with_user_id(self):
        fs = _make_fs()
        fs.get_recent_ai_conversation = AsyncMock(return_value=None)
        svc = AIConversationService(firestore_service=fs)
        await svc.get_recent_session_summary("u1")
        fs.get_recent_ai_conversation.assert_called_once_with("u1")

    async def test_unknown_final_stage_returns_none(self):
        """If the stored stage value doesn't map to a known enum, return None."""
        conv = self._make_recent_conv(minutes_ago=5)
        conv["final_stage"] = "unknown_stage_xyz"
        fs = _make_fs()
        fs.get_recent_ai_conversation = AsyncMock(return_value=conv)
        svc = AIConversationService(firestore_service=fs)
        result = await svc.get_recent_session_summary("u1")
        assert result is None
