"""
Unit tests for ResponseOrchestrator.
Tests the conversation flow and provider search timing.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch

from ai_assistant.services import ConversationStage
from ai_assistant.services.response_orchestrator import ResponseOrchestrator


@pytest.fixture
def mock_llm_service():
    """Mock LLM service."""
    service = Mock()
    
    async def mock_generate_stream(*args, **kwargs):
        yield "Test "
        yield "response"
    
    service.generate_stream = mock_generate_stream
    return service


@pytest.fixture
def mock_conversation_service():
    """Mock conversation service."""
    service = Mock()
    service.get_current_stage = Mock(return_value=ConversationStage.TRIAGE)
    service.accumulate_problem_description = AsyncMock()
    service.search_providers_for_request = AsyncMock()
    service.detect_stage_transition = AsyncMock(return_value=None)
    service.set_stage = Mock()
    service.create_prompt_for_stage = Mock(return_value="prompt")
    service.context = {
        "user_problem": "",
        "detected_category": None,
        "providers_found": [],
        "current_provider_index": 0,
    }
    return service


@pytest.fixture
def orchestrator(mock_llm_service, mock_conversation_service):
    """Create ResponseOrchestrator instance."""
    return ResponseOrchestrator(
        llm_service=mock_llm_service,
        conversation_service=mock_conversation_service
    )


class TestProviderSearchTiming:
    """Test that provider search happens at the correct stage."""
    
    @pytest.mark.asyncio
    async def test_no_search_during_triage_stage(self, orchestrator, mock_conversation_service):
        """Test that provider search is NOT called during TRIAGE stage."""
        # Setup: conversation is in TRIAGE stage
        mock_conversation_service.get_current_stage.return_value = ConversationStage.TRIAGE
        mock_conversation_service.detect_stage_transition.return_value = None
        
        # Execute: generate response in TRIAGE stage
        user_input = "Ich brauche einen Elektriker für mein Haus"
        response_chunks = []
        async for chunk in orchestrator.generate_response_stream(user_input, "test-session"):
            response_chunks.append(chunk)
        
        # Verify: accumulate was called, but search was NOT called
        mock_conversation_service.accumulate_problem_description.assert_called_once_with(user_input)
        mock_conversation_service.search_providers_for_request.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_search_when_entering_finalize_stage(self, orchestrator, mock_conversation_service, mock_llm_service):
        """Test that provider search IS called when transitioning to FINALIZE stage."""
        # Setup: conversation is in TRIAGE, will transition to FINALIZE
        mock_conversation_service.get_current_stage.return_value = ConversationStage.TRIAGE
        mock_conversation_service.detect_stage_transition.return_value = ConversationStage.FINALIZE
        
        # Mock provider search to populate context
        async def mock_search():
            mock_conversation_service.context["providers_found"] = [
                {"provider_id": "p1", "name": "Provider 1"}
            ]
        mock_conversation_service.search_providers_for_request = AsyncMock(side_effect=mock_search)
        
        # Execute: generate response that triggers stage transition
        user_input = "Ich brauche einen Elektriker"
        response_chunks = []
        async for chunk in orchestrator.generate_response_stream(user_input, "test-session"):
            response_chunks.append(chunk)
        
        # Verify: search was called when entering FINALIZE
        mock_conversation_service.search_providers_for_request.assert_called_once()
        mock_conversation_service.set_stage.assert_called_with(ConversationStage.FINALIZE)
    
    @pytest.mark.asyncio
    async def test_finalize_presentation_after_search(self, orchestrator, mock_conversation_service):
        """Test that provider presentation is generated after search in FINALIZE."""
        # Setup: transition to FINALIZE detected
        mock_conversation_service.get_current_stage.return_value = ConversationStage.TRIAGE
        mock_conversation_service.detect_stage_transition.return_value = ConversationStage.FINALIZE
        
        # Mock search to add providers
        async def mock_search():
            mock_conversation_service.context["providers_found"] = [
                {"provider_id": "p1", "name": "Test Provider", "description": "Great service"}
            ]
        mock_conversation_service.search_providers_for_request = AsyncMock(side_effect=mock_search)
        
        # Execute
        user_input = "Ich brauche einen Klempner"
        response_chunks = []
        async for chunk in orchestrator.generate_response_stream(user_input, "test-session"):
            response_chunks.append(chunk)
        
        # Verify: search was called before generating finalize presentation
        mock_conversation_service.search_providers_for_request.assert_called_once()
        # Verify: create_prompt_for_stage was called for FINALIZE stage
        assert any(
            call[0][0] == ConversationStage.FINALIZE 
            for call in mock_conversation_service.create_prompt_for_stage.call_args_list
        )


class TestConversationFlowIntegration:
    """Test the complete conversation flow."""
    
    @pytest.mark.asyncio
    async def test_full_triage_to_finalize_flow(self, orchestrator, mock_conversation_service):
        """Test complete flow from TRIAGE to FINALIZE with correct search timing."""
        # Setup: Start in TRIAGE
        mock_conversation_service.get_current_stage.return_value = ConversationStage.TRIAGE
        
        # First call: TRIAGE stage, no transition
        mock_conversation_service.detect_stage_transition.return_value = None
        
        user_input_1 = "Mein Wasserhahn ist kaputt"
        async for _ in orchestrator.generate_response_stream(user_input_1, "test-session"):
            pass
        
        # Verify: accumulate called, no search
        assert mock_conversation_service.accumulate_problem_description.call_count == 1
        assert mock_conversation_service.search_providers_for_request.call_count == 0
        
        # Second call: Still TRIAGE, will transition to FINALIZE
        mock_conversation_service.detect_stage_transition.return_value = ConversationStage.FINALIZE
        
        async def mock_search():
            mock_conversation_service.context["providers_found"] = [
                {"provider_id": "p1", "name": "Plumber Joe"}
            ]
        mock_conversation_service.search_providers_for_request = AsyncMock(side_effect=mock_search)
        
        user_input_2 = "Es ist dringend"
        async for _ in orchestrator.generate_response_stream(user_input_2, "test-session"):
            pass
        
        # Verify: accumulate called again, search called once when entering FINALIZE
        assert mock_conversation_service.accumulate_problem_description.call_count == 2
        assert mock_conversation_service.search_providers_for_request.call_count == 1
    
    @pytest.mark.asyncio
    async def test_no_search_in_greeting_stage(self, orchestrator, mock_conversation_service):
        """Test that search is not called in GREETING stage."""
        # Setup: conversation in GREETING stage
        mock_conversation_service.get_current_stage.return_value = ConversationStage.GREETING
        mock_conversation_service.detect_stage_transition.return_value = None
        
        # Execute
        user_input = "Hallo"
        async for _ in orchestrator.generate_response_stream(user_input, "test-session"):
            pass
        
        # Verify: neither accumulate nor search were called
        mock_conversation_service.accumulate_problem_description.assert_not_called()
        mock_conversation_service.search_providers_for_request.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_no_double_search_in_finalize(self, orchestrator, mock_conversation_service):
        """Test that search is not called again if already in FINALIZE stage."""
        # Setup: already in FINALIZE stage
        mock_conversation_service.get_current_stage.return_value = ConversationStage.FINALIZE
        mock_conversation_service.detect_stage_transition.return_value = None
        mock_conversation_service.context["providers_found"] = [
            {"provider_id": "p1", "name": "Provider 1"}
        ]
        
        # Execute
        user_input = "Ja, das klingt gut"
        async for _ in orchestrator.generate_response_stream(user_input, "test-session"):
            pass
        
        # Verify: search was NOT called (already searched when entering FINALIZE)
        mock_conversation_service.search_providers_for_request.assert_not_called()
        # Verify: accumulate was NOT called (not in TRIAGE)
        mock_conversation_service.accumulate_problem_description.assert_not_called()


class TestStageTransitionDetection:
    """Test stage transition detection and handling."""
    
    @pytest.mark.asyncio
    async def test_stage_transition_updates_stage(self, orchestrator, mock_conversation_service):
        """Test that detected stage transition updates the conversation stage."""
        # Setup
        mock_conversation_service.get_current_stage.return_value = ConversationStage.TRIAGE
        mock_conversation_service.detect_stage_transition.return_value = ConversationStage.FINALIZE
        
        async def mock_search():
            pass
        mock_conversation_service.search_providers_for_request = AsyncMock(side_effect=mock_search)
        
        # Execute
        user_input = "Test"
        async for _ in orchestrator.generate_response_stream(user_input, "test-session"):
            pass
        
        # Verify: set_stage was called with FINALIZE
        mock_conversation_service.set_stage.assert_called_with(ConversationStage.FINALIZE)
    
    @pytest.mark.asyncio
    async def test_no_stage_change_without_transition(self, orchestrator, mock_conversation_service):
        """Test that stage is not changed when no transition is detected."""
        # Setup: no transition
        mock_conversation_service.get_current_stage.return_value = ConversationStage.TRIAGE
        mock_conversation_service.detect_stage_transition.return_value = None
        
        # Execute
        user_input = "Test"
        async for _ in orchestrator.generate_response_stream(user_input, "test-session"):
            pass
        
        # Verify: set_stage was not called
        mock_conversation_service.set_stage.assert_not_called()
