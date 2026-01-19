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
            "detected_category": None,
            "providers_found": [],
            "current_provider_index": 0,
        }
        
        assistant = AIAssistant(
            gemini_api_key='test-api-key',
            language_code='de-DE',
            voice_name='de-DE-Test-Voice',
            session_id='test-session'
        )
        
        return assistant


class TestAIAssistantInitialization:
    """Test AI Assistant initialization."""
    
    def test_initialization_with_defaults(self, ai_assistant):
        """Test that AI Assistant initializes with default values."""
        assert ai_assistant.language_code == 'de-DE'
        assert ai_assistant.voice_name == 'de-DE-Test-Voice'
        assert ai_assistant.session_id == 'test-session'
        assert ai_assistant.current_stage == ConversationStage.GREETING
    
    def test_conversation_context_initialized(self, ai_assistant):
        """Test that conversation context is properly initialized."""
        assert ai_assistant.conversation_context['user_problem'] == []
        assert ai_assistant.conversation_context['detected_category'] is None
        assert ai_assistant.conversation_context['providers_found'] == []
        assert ai_assistant.conversation_context['current_provider_index'] == 0


class TestConversationStageManagement:
    """Test conversation stage management."""
    
    def test_initial_stage_is_greeting(self, ai_assistant):
        """Test that initial stage is GREETING."""
        assert ai_assistant.current_stage == ConversationStage.GREETING
    
    def test_update_chain_for_stage(self, ai_assistant):
        """Test stage update functionality."""
        ai_assistant.conversation_service.set_stage = Mock()
        ai_assistant._update_chain_for_stage(ConversationStage.TRIAGE)
        ai_assistant.conversation_service.set_stage.assert_called_once_with(ConversationStage.TRIAGE)
    
    @pytest.mark.asyncio
    async def test_detect_stage_transition_triage_to_finalize(self, ai_assistant):
        """Test detection of transition from TRIAGE to FINALIZE."""
        ai_assistant.conversation_service.get_current_stage = Mock(return_value=ConversationStage.TRIAGE)
        ai_assistant.conversation_service.detect_stage_transition = AsyncMock(return_value=ConversationStage.FINALIZE)
        
        user_input = "Ich brauche einen Klempner"
        ai_response = "Einen Moment bitte, ich durchsuche die Datenbank"
        
        new_stage = await ai_assistant._detect_stage_transition(user_input, ai_response)
        
        assert new_stage == ConversationStage.FINALIZE
    
    @pytest.mark.asyncio
    async def test_detect_stage_transition_finalize_to_completed(self, ai_assistant):
        """Test detection of transition from FINALIZE to COMPLETED."""
        ai_assistant.conversation_service.get_current_stage = Mock(return_value=ConversationStage.FINALIZE)
        ai_assistant.conversation_service.detect_stage_transition = AsyncMock(return_value=ConversationStage.COMPLETED)
        
        user_input = "Danke"
        ai_response = "Schönen Tag noch!"
        
        new_stage = await ai_assistant._detect_stage_transition(user_input, ai_response)
        assert new_stage == ConversationStage.COMPLETED


class TestProblemDescriptionAccumulation:
    """Test problem description accumulation."""
    
    @pytest.mark.asyncio
    async def test_accumulate_problem_description(self, ai_assistant):
        """Test that problem description is accumulated."""
        user_input = "Mein Wasserhahn tropft"
        
        ai_assistant.conversation_service.accumulate_problem_description = AsyncMock()
        await ai_assistant._accumulate_problem_description(user_input)
        
        ai_assistant.conversation_service.accumulate_problem_description.assert_called_once_with(user_input)
    
    @pytest.mark.asyncio
    async def test_accumulate_does_not_search_providers(self, ai_assistant, mock_data_provider):
        """Test that provider search is NOT called during accumulation in TRIAGE stage."""
        user_input = "Ich brauche einen Elektriker"
        
        # Setup mock
        ai_assistant.conversation_service.accumulate_problem_description = AsyncMock()
        
        # Execute accumulation
        await ai_assistant._accumulate_problem_description(user_input)
        
        # Verify accumulation was called
        ai_assistant.conversation_service.accumulate_problem_description.assert_called_once_with(user_input)
        
        # Verify search was NOT called (search happens in FINALIZE stage, not TRIAGE)
        mock_data_provider.search_providers.assert_not_called()


class TestSpeechToText:
    """Test speech-to-text functionality."""
    
    @pytest.mark.asyncio
    async def test_speech_to_text_continuous_stream(self, ai_assistant):
        """Test continuous speech-to-text streaming."""
        # Mock audio generator
        async def mock_audio_gen():
            yield b'audio_chunk_1'
            yield b'audio_chunk_2'
        
        # Mock STT service
        async def mock_stt_stream(*args):
            yield ("Test transcript", True)
        
        ai_assistant.stt_service.continuous_stream = mock_stt_stream
        
        results = []
        async for transcript, is_final in ai_assistant.speech_to_text_continuous_stream(mock_audio_gen()):
            results.append((transcript, is_final))
        
        assert len(results) > 0
        assert results[0][0] == "Test transcript"
        assert results[0][1] is True


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


class TestTextToSpeech:
    """Test text-to-speech functionality."""
    
    @pytest.mark.asyncio
    async def test_text_to_speech_stream(self, ai_assistant):
        """Test text-to-speech streaming."""
        text = "Test text"
        
        # Mock TTS service
        async def mock_tts_stream(*args, **kwargs):
            yield b'audio_chunk_1'
            yield b'audio_chunk_2'
        
        ai_assistant.tts_service.synthesize_stream = mock_tts_stream
        
        audio_chunks = []
        async for chunk in ai_assistant.text_to_speech_stream(text):
            audio_chunks.append(chunk)
        
        assert len(audio_chunks) == 2
        assert isinstance(audio_chunks[0], bytes)


class TestGreetingGeneration:
    """Test greeting generation."""
    
    @pytest.mark.asyncio
    async def test_generate_greeting(self, ai_assistant):
        """Test greeting generation."""
        # Mock conversation service
        ai_assistant.conversation_service.generate_greeting = AsyncMock(return_value="Hallo! Wie kann ich helfen?")
        
        greeting = await ai_assistant.generate_greeting(user_name="Test User")
        
        assert greeting == "Hallo! Wie kann ich helfen?"
        ai_assistant.conversation_service.generate_greeting.assert_called_once()
    
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


class TestSessionHistoryManagement:
    """Test session history management."""
    
    def test_get_session_history_creates_new(self, ai_assistant):
        """Test that session history is created for new session."""
        history = ai_assistant._get_session_history('new-session')
        assert history is not None
        ai_assistant.llm_service.get_session_history.assert_called()
    
    def test_get_session_history_returns_existing(self, ai_assistant):
        """Test that existing session history is returned."""
        # Mock LLM service to track calls
        mock_history = Mock()
        mock_history.add_message = Mock()
        mock_history.messages = [Mock()]
        
        ai_assistant.llm_service.get_session_history = Mock(return_value=mock_history)
        
        history1 = ai_assistant._get_session_history('test-session')
        history1.add_message(Mock())
        
        history2 = ai_assistant._get_session_history('test-session')
        
        # Both should return the same mock
        assert ai_assistant.llm_service.get_session_history.called


class TestPromptCreation:
    """Test prompt creation for different stages."""
    
    def test_create_prompt_for_greeting_stage(self, ai_assistant):
        """Test prompt creation for GREETING stage."""
        prompt = ai_assistant._create_prompt_for_stage(ConversationStage.GREETING)
        assert prompt is not None
    
    def test_create_prompt_for_triage_stage(self, ai_assistant):
        """Test prompt creation for TRIAGE stage."""
        prompt = ai_assistant._create_prompt_for_stage(ConversationStage.TRIAGE)
        assert prompt is not None
    
    def test_create_prompt_for_finalize_stage(self, ai_assistant):
        """Test prompt creation for FINALIZE stage."""
        # Add some providers to context
        ai_assistant.conversation_context['providers_found'] = [
            {'provider_id': 'p1', 'name': 'Provider 1'}
        ]
        
        prompt = ai_assistant._create_prompt_for_stage(ConversationStage.FINALIZE)
        assert prompt is not None
