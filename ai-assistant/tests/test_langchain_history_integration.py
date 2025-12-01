"""
Test LangChain RunnableWithMessageHistory integration with PersistentChatMessageHistory.

Verifies that RunnableWithMessageHistory automatically calls add_message() for both
user input and AI responses, ensuring proper persistence to Weaviate.
"""
import pytest
import logging
from unittest.mock import patch
from langchain_core.messages import AIMessage, HumanMessage

from src.ai_assistant.ai_assistant import PersistentChatMessageHistory

logger = logging.getLogger(__name__)


class TestPersistentChatMessageHistory:
    """Test PersistentChatMessageHistory persistence behavior."""

    def test_add_message_saves_to_weaviate(self):
        """Verify that add_message persists to Weaviate for new messages."""
        
        with patch('src.ai_assistant.ai_assistant.ChatMessageModelWeaviate.save_message') as mock_save:
            history = PersistentChatMessageHistory(
                user_id="test_user_123",
                session_id="test_session",
                stage_getter=lambda: "TRIAGE"
            )
            
            # Add a human message
            history.add_message(HumanMessage(content="Hello"))
            
            # Verify save was called
            assert mock_save.call_count == 1
            assert mock_save.call_args[1]['role'] == 'human'
            assert mock_save.call_args[1]['content'] == 'Hello'
            assert mock_save.call_args[1]['user_id'] == 'test_user_123'
            assert mock_save.call_args[1]['session_id'] == 'test_session'
            assert mock_save.call_args[1]['stage'] == 'TRIAGE'
            
            # Add an AI message
            history.add_message(AIMessage(content="Hi there!"))
            
            # Verify save was called again
            assert mock_save.call_count == 2
            assert mock_save.call_args[1]['role'] == 'assistant'
            assert mock_save.call_args[1]['content'] == 'Hi there!'
            
            # Verify messages are in memory
            assert len(history.messages) == 2
            assert history.messages[0].content == "Hello"
            assert history.messages[1].content == "Hi there!"

    def test_history_not_saved_during_loading(self):
        """Verify that messages loaded from Weaviate don't trigger duplicate saves."""
        
        # Mock existing messages in Weaviate
        existing_messages = [
            {"role": "human", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"}
        ]
        
        with patch('src.ai_assistant.ai_assistant.ChatMessageModelWeaviate.get_messages', return_value=existing_messages), \
             patch('src.ai_assistant.ai_assistant.ChatMessageModelWeaviate.save_message') as mock_save:
            
            # Create history and load from store
            history = PersistentChatMessageHistory(
                user_id="test_user_789",
                session_id="test_session_3",
                stage_getter=lambda: "TRIAGE"
            )
            history.load_from_store()
            
            # Verify messages were loaded
            assert len(history.messages) == 2
            assert history.messages[0].content == "Previous question"
            assert history.messages[1].content == "Previous answer"
            
            # Verify save_message was NOT called during loading
            assert mock_save.call_count == 0, "save_message should not be called when loading from store"
            
            # Now add a new message
            history.add_message(HumanMessage(content="New question"))
            
            # Verify save_message IS called for new messages
            assert mock_save.call_count == 1
            assert mock_save.call_args[1]['content'] == "New question"

    def test_no_save_when_user_id_missing(self):
        """Verify that messages aren't saved when user_id is not set."""
        
        with patch('src.ai_assistant.ai_assistant.ChatMessageModelWeaviate.save_message') as mock_save:
            # Create history without user_id
            history = PersistentChatMessageHistory(
                user_id="",
                session_id="test_session",
                stage_getter=lambda: "TRIAGE"
            )
            
            # Add a message
            history.add_message(HumanMessage(content="Hello"))
            
            # Verify save was NOT called (no user_id)
            assert mock_save.call_count == 0
            
            # But message is still in memory
            assert len(history.messages) == 1
            assert history.messages[0].content == "Hello"

    def test_empty_content_not_saved(self):
        """Verify that messages with empty content are not saved to Weaviate."""
        
        with patch('src.ai_assistant.ai_assistant.ChatMessageModelWeaviate.save_message') as mock_save:
            history = PersistentChatMessageHistory(
                user_id="test_user_456",
                session_id="test_session",
                stage_getter=lambda: "TRIAGE"
            )
            
            # Add a message with empty content
            history.add_message(HumanMessage(content=""))
            
            # Verify save was NOT called (empty content)
            assert mock_save.call_count == 0
            
            # But message is still in memory
            assert len(history.messages) == 1

    def test_stage_getter_called_on_save(self):
        """Verify that stage_getter is called when saving messages."""
        
        stages = ["GREETING", "TRIAGE", "FINALIZE"]
        stage_index = [0]
        
        def get_stage():
            current = stages[stage_index[0]]
            stage_index[0] = min(stage_index[0] + 1, len(stages) - 1)
            return current
        
        with patch('src.ai_assistant.ai_assistant.ChatMessageModelWeaviate.save_message') as mock_save:
            history = PersistentChatMessageHistory(
                user_id="test_user_999",
                session_id="test_session",
                stage_getter=get_stage
            )
            
            # Add messages in different stages
            history.add_message(HumanMessage(content="First"))
            history.add_message(AIMessage(content="Second"))
            history.add_message(HumanMessage(content="Third"))
            
            # Verify stages were captured correctly
            assert mock_save.call_count == 3
            assert mock_save.call_args_list[0][1]['stage'] == "GREETING"
            assert mock_save.call_args_list[1][1]['stage'] == "TRIAGE"
            assert mock_save.call_args_list[2][1]['stage'] == "FINALIZE"

