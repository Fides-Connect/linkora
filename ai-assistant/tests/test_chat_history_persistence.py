"""Unit tests for persistent chat history integration."""
import pytest
import sys
import os
from unittest.mock import patch

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ai_assistant.ai_assistant import (
    PersistentChatMessageHistory,
    ConversationStage,
)
from langchain_core.messages import HumanMessage, AIMessage


def test_history_loads_existing_messages():
    """Existing persisted messages should hydrate in-memory history."""
    messages = [
        {"content": "Hallo", "role": "human", "timestamp": "2024-01-01T00:00:00"},
        {"content": "Willkommen!", "role": "assistant", "timestamp": "2024-01-01T00:00:01"},
    ]
    with patch('ai_assistant.ai_assistant.ChatMessageModelWeaviate') as mock_model:
        mock_model.get_messages.return_value = messages
        history = PersistentChatMessageHistory(
            user_id='user_1',
            session_id='user_1',
            stage_getter=lambda: ConversationStage.TRIAGE,
        )
        history.load_from_store()
        assert len(history.messages) == 2
        mock_model.get_messages.assert_called_once_with('user_1')
        mock_model.save_message.assert_not_called()


def test_add_message_persists_to_weaviate():
    """Adding messages should persist them unless loading."""
    with patch('ai_assistant.ai_assistant.ChatMessageModelWeaviate') as mock_model:
        mock_model.get_messages.return_value = []
        history = PersistentChatMessageHistory(
            user_id='user_2',
            session_id='user_2',
            stage_getter=lambda: ConversationStage.TRIAGE,
        )
        history.load_from_store()
        history.add_message(HumanMessage(content='Ich brauche Hilfe.'))
        history.add_message(AIMessage(content='Natürlich, wie kann ich unterstützen?'))
        assert mock_model.save_message.call_count == 2
        mock_model.save_message.assert_any_call(
            user_id='user_2',
            session_id='user_2',
            role='human',
            content='Ich brauche Hilfe.',
            stage=ConversationStage.TRIAGE,
        )
        mock_model.save_message.assert_any_call(
            user_id='user_2',
            session_id='user_2',
            role='assistant',
            content='Natürlich, wie kann ich unterstützen?',
            stage=ConversationStage.TRIAGE,
        )