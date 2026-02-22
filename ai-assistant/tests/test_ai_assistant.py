"""
Unit tests for AI Assistant core functionality.
"""
import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from langchain_core.messages import AIMessage, HumanMessage

from ai_assistant.ai_assistant import AIAssistant
from ai_assistant.services import ConversationStage


@pytest.fixture
def mock_data_provider():
    """Mock data provider for testing."""
    provider = Mock()
    provider.get_user_by_id = AsyncMock(return_value={
        'user_id': 'test123',
        'name': 'Test User',
        'has_open_request': False
    })
    provider.search_providers = AsyncMock(return_value=[
        {
            'provider_id': 'p1',
            'name': 'Provider 1',
            'description': 'Test provider 1'
        }
    ])
    provider.get_provider_by_id = AsyncMock(return_value={
        'provider_id': 'p1',
        'name': 'Provider 1'
    })
    return provider


@pytest.fixture
def ai_assistant(mock_data_provider):
    """Create AI Assistant instance with mocked dependencies."""
    with patch('ai_assistant.ai_assistant.get_data_provider', return_value=mock_data_provider), \
         patch('ai_assistant.ai_assistant.SpeechToTextService') as mock_stt, \
         patch('ai_assistant.ai_assistant.TextToSpeechService') as mock_tts, \
         patch('ai_assistant.ai_assistant.LLMService') as mock_llm, \
         patch('ai_assistant.ai_assistant.ConversationService') as mock_conv:
        
        # Setup mock service instances
        mock_stt_instance = Mock()
        mock_tts_instance = Mock()
        mock_llm_instance = Mock()
        mock_conv_instance = Mock()
        
        mock_stt.return_value = mock_stt_instance
        mock_tts.return_value = mock_tts_instance
        mock_llm.return_value = mock_llm_instance
        mock_conv.return_value = mock_conv_instance
        
        # Setup conversation service properties
        mock_conv_instance.get_current_stage = Mock(return_value=ConversationStage.GREETING)
        mock_conv_instance.context = {
            "user_problem": [],
            "providers_found": [],
            "current_provider_index": 0,
        }
        
        assistant = AIAssistant(
            gemini_api_key='test-api-key',
            language='de',
            session_id='test-session'
        )
        
        return assistant


class TestAIAssistantInitialization:
    """Test AI Assistant initialization."""
    
    def test_initialization_with_defaults(self, ai_assistant):
        """Test that AI Assistant initializes with default values."""
        assert ai_assistant.language_code == 'de-DE'
        assert ai_assistant.voice_name == 'de-DE-Chirp3-HD-Sulafat'
        assert ai_assistant.session_id == 'test-session'


class TestAIAssistantCapabilityWiring:
    """generate_llm_response_stream must include all 5 tool capability grants."""

    async def test_provider_onboarding_capability_in_context(self, ai_assistant):
        from ai_assistant.services.agent_tools import ToolCapability
        captured_contexts = []

        async def capture_context(user_input, session_id, context=None):
            captured_contexts.append(context or {})
            if False:
                yield ""

        ai_assistant.response_orchestrator.generate_response_stream = capture_context

        async for _ in ai_assistant.generate_llm_response_stream("hi", user_id="u1"):
            pass

        assert captured_contexts, "generate_response_stream was not called"
        caps = captured_contexts[0].get("user_capabilities", [])
        assert ToolCapability("provider_onboarding", "write") in caps

    async def test_all_five_capabilities_present(self, ai_assistant):
        from ai_assistant.services.agent_tools import ToolCapability
        captured_contexts = []

        async def capture_context(user_input, session_id, context=None):
            captured_contexts.append(context or {})
            if False:
                yield ""

        ai_assistant.response_orchestrator.generate_response_stream = capture_context

        async for _ in ai_assistant.generate_llm_response_stream("hi", user_id="u1"):
            pass

        caps = captured_contexts[0].get("user_capabilities", [])
        expected = [
            ToolCapability("providers", "read"),
            ToolCapability("favorites", "read"),
            ToolCapability("service_requests", "read"),
            ToolCapability("service_requests", "write"),
            ToolCapability("provider_onboarding", "write"),
        ]
        for cap in expected:
            assert cap in caps, f"Missing capability: {cap}"

class TestLLMResponseGeneration:
    """Test LLM response generation."""
    
    @pytest.mark.asyncio
    async def test_generate_llm_response_stream(self, ai_assistant):
        """Test LLM response streaming."""
        prompt = "Test prompt"
        
        # Mock LLM service streaming
        async def mock_llm_stream(*args, **kwargs):
            yield "Hello "
            yield "world"
        
        ai_assistant.llm_service.generate_stream = mock_llm_stream
        ai_assistant.conversation_service.detect_stage_transition = AsyncMock(return_value=None)
        
        # Collect response chunks
        response_chunks = []
        async for chunk in ai_assistant.generate_llm_response_stream(prompt):
            response_chunks.append(chunk)
        
        assert len(response_chunks) == 2
        assert ''.join(response_chunks) == "Hello world"

class TestGreetingGeneration:
    """Test greeting generation."""
    
    @pytest.mark.asyncio
    async def test_get_greeting_audio(self, ai_assistant, mock_data_provider):
        """Test getting greeting with audio."""
        # Mock conversation service
        ai_assistant.conversation_service.generate_greeting = AsyncMock(return_value="Hallo!")
        
        # Mock TTS service - must accept chunk_size parameter
        async def mock_tts_stream(*args, **kwargs):
            yield b'audio_data'
        
        ai_assistant.tts_service.synthesize_stream = mock_tts_stream
        
        greeting_text, audio_stream = await ai_assistant.get_greeting_audio(user_id='test123')
        
        assert greeting_text == "Hallo!"
        assert audio_stream is not None
        
        # Verify user data was fetched
        mock_data_provider.get_user_by_id.assert_called_once_with('test123')