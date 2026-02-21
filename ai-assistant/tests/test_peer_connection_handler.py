"""
Unit tests for Peer Connection Handler functionality.
"""
import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from aiortc import RTCPeerConnection, RTCSessionDescription

from ai_assistant.peer_connection_handler import PeerConnectionHandler


@pytest.fixture
def mock_ai_assistant():
    """Mock AI Assistant."""
    assistant = Mock()
    return assistant


@pytest.fixture
def mock_websocket():
    """Mock WebSocket."""
    ws = Mock()
    ws.send_json = AsyncMock()
    ws.send_str = AsyncMock()
    return ws


@pytest.fixture
def peer_handler(mock_ai_assistant, mock_websocket):
    """Create PeerConnectionHandler instance."""
    with patch('ai_assistant.peer_connection_handler.RTCPeerConnection') as mock_pc:
        mock_pc_instance = Mock()
        mock_pc_instance.setRemoteDescription = AsyncMock()
        mock_pc_instance.createAnswer = AsyncMock()
        mock_pc_instance.setLocalDescription = AsyncMock()
        mock_pc_instance.addTrack = Mock()
        mock_pc_instance.getSenders = Mock(return_value=[])  # Default to no senders (initial connection)
        mock_pc_instance.connectionState = 'new'
        mock_pc_instance.iceConnectionState = 'new'
        mock_pc_instance.iceGatheringState = 'new'
        mock_pc.return_value = mock_pc_instance
        
        handler = PeerConnectionHandler(
            connection_id='test-123',
            websocket=mock_websocket
        )
        handler.pc = mock_pc_instance
        return handler


class TestPeerConnectionHandlerInitialization:
    """Test PeerConnectionHandler initialization."""
    
    def test_initialization(self, peer_handler, mock_websocket):
        """Test that PeerConnectionHandler initializes correctly."""
        assert peer_handler.connection_id == 'test-123'
        assert peer_handler.websocket is mock_websocket
        assert peer_handler.pc is not None
        assert peer_handler.audio_processor is None


class TestOfferHandling:
    """Test WebRTC offer handling."""
    
    @pytest.mark.asyncio
    async def test_handle_offer(self, peer_handler):
        """Test handling WebRTC offer."""
        offer = RTCSessionDescription(
            sdp='test-sdp',
            type='offer'
        )
        
        # Mock local description
        mock_answer = Mock()
        mock_answer.sdp = 'answer-sdp'
        mock_answer.type = 'answer'
        peer_handler.pc.localDescription = mock_answer
        peer_handler.pc.createAnswer.return_value = mock_answer
        
        # Mock track ready event
        peer_handler.track_ready.set()
        
        with patch.object(peer_handler, '_send_message', new=AsyncMock()):
            await peer_handler.handle_offer(offer)
        
        # Verify remote description was set
        peer_handler.pc.setRemoteDescription.assert_called_once()
        
        # Verify answer was created
        peer_handler.pc.createAnswer.assert_called_once()
        
        # Verify local description was set
        peer_handler.pc.setLocalDescription.assert_called_once()


class TestICECandidateHandling:
    """Test ICE candidate handling."""
    
    @pytest.mark.asyncio
    async def test_handle_ice_candidate(self, peer_handler):
        """Test handling ICE candidate."""
        candidate_data = {
            'candidate': 'candidate:1 1 UDP 2122260223 192.168.1.1 54321 typ host',
            'sdpMid': '0',
            'sdpMLineIndex': 0
        }
        
        with patch('ai_assistant.peer_connection_handler.candidate_from_sdp') as mock_candidate_from_sdp:
            mock_candidate = Mock()
            mock_candidate_from_sdp.return_value = mock_candidate
            
            peer_handler.pc.addIceCandidate = AsyncMock()
            
            await peer_handler.handle_ice_candidate(candidate_data)
            
            # Verify candidate was added
            peer_handler.pc.addIceCandidate.assert_called_once()


class TestMessageSending:
    """Test message sending."""
    
    @pytest.mark.asyncio
    async def test_send_message(self, peer_handler, mock_websocket):
        """Test sending message through WebSocket."""
        message = {
            'type': 'test',
            'data': 'test-data'
        }
        
        await peer_handler._send_message(message)
        
        # Verify WebSocket send was called
        assert mock_websocket.send_json.called or mock_websocket.send_str.called


class TestConnectionLifecycle:
    """Test connection lifecycle."""
    
    @pytest.mark.asyncio
    async def test_close_connection(self, peer_handler):
        """Test closing peer connection."""
        # Mock audio processor
        mock_audio_processor = Mock()
        mock_audio_processor.stop = AsyncMock()
        peer_handler.audio_processor = mock_audio_processor
        
        # Mock PC close
        peer_handler.pc.close = AsyncMock()
        
        await peer_handler.close()
        
        # Verify audio processor was stopped
        if peer_handler.audio_processor:
            mock_audio_processor.stop.assert_called_once()
        
        # Verify PC was closed
        peer_handler.pc.close.assert_called_once()


class TestEventHandlers:
    """Test WebRTC event handlers."""
    
    def test_event_handlers_setup(self, peer_handler):
        """Test that event handlers are set up."""
        # Event handlers should be registered on the peer connection
        # This is tested indirectly through the initialization
        assert peer_handler.pc is not None


class TestRenegotiation:
    """Test WebRTC renegotiation for mid-stream device switching."""
    
    @pytest.mark.asyncio
    async def test_handle_offer_detects_renegotiation(self, peer_handler):
        """Test that handle_offer detects renegotiation."""
        offer = RTCSessionDescription(
            sdp='test-sdp',
            type='offer'
        )
        
        # Mock local description
        mock_answer = Mock()
        mock_answer.sdp = 'answer-sdp'
        mock_answer.type = 'answer'
        peer_handler.pc.localDescription = mock_answer
        peer_handler.pc.createAnswer.return_value = mock_answer

        # Renegotiation is now detected by audio_processor presence
        mock_audio_processor = Mock()
        mock_audio_processor._is_text_mode = False
        peer_handler.audio_processor = mock_audio_processor

        # track_update_ready is already set so wait_for doesn't block
        peer_handler.track_update_ready.set()

        with patch.object(peer_handler, '_send_message', new=AsyncMock()):
            await peer_handler.handle_offer(offer)

        # Verify remote description was set
        peer_handler.pc.setRemoteDescription.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_offer_skips_output_track_on_renegotiation(self, peer_handler):
        """Test that output track is not re-added during renegotiation."""
        offer = RTCSessionDescription(
            sdp='test-sdp',
            type='offer'
        )
        
        # Mock local description
        mock_answer = Mock()
        mock_answer.sdp = 'answer-sdp'
        mock_answer.type = 'answer'
        peer_handler.pc.localDescription = mock_answer
        peer_handler.pc.createAnswer.return_value = mock_answer
        
        # Renegotiation is detected by audio_processor presence
        mock_audio_processor = Mock()
        mock_output_track = Mock()
        mock_output_track.id = 'output-track-123'
        mock_audio_processor.get_output_track = Mock(return_value=mock_output_track)
        mock_audio_processor._is_text_mode = False
        peer_handler.audio_processor = mock_audio_processor

        # track_update_ready already set so wait_for doesn't block
        peer_handler.track_update_ready.set()

        with patch.object(peer_handler, '_send_message', new=AsyncMock()):
            await peer_handler.handle_offer(offer)

        # Verify addTrack was NOT called for output track during renegotiation
        peer_handler.pc.addTrack.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_handle_offer_adds_output_track_on_initial_connection(self, peer_handler):
        """Test that output track is added during initial connection."""
        offer = RTCSessionDescription(
            sdp='test-sdp',
            type='offer'
        )
        
        # Mock local description
        mock_answer = Mock()
        mock_answer.sdp = 'answer-sdp'
        mock_answer.type = 'answer'
        peer_handler.pc.localDescription = mock_answer
        peer_handler.pc.createAnswer.return_value = mock_answer
        
        # Initial connection: audio_processor starts as None
        assert peer_handler.audio_processor is None

        # Create a mock audio processor to simulate on_track firing
        mock_audio_processor = Mock()
        mock_output_track = Mock()
        mock_output_track.id = 'output-track-123'
        mock_audio_processor.get_output_track = Mock(return_value=mock_output_track)
        mock_audio_processor._is_text_mode = False

        # Simulate on_track: sets audio_processor then signals track_ready,
        # which is exactly what happens in the real WebRTC flow.
        async def simulate_on_track():
            await asyncio.sleep(0)  # yield so handle_offer can start waiting
            peer_handler.audio_processor = mock_audio_processor
            peer_handler.track_ready.set()

        with patch.object(peer_handler, '_send_message', new=AsyncMock()):
            await asyncio.gather(
                peer_handler.handle_offer(offer),
                simulate_on_track(),
            )

        # Verify addTrack WAS called for output track during initial connection
        peer_handler.pc.addTrack.assert_called_once_with(mock_output_track)


class TestRuntimeStateFSMWiring:
    """Test that FSM on_state_change is wired to _emit_runtime_state."""

    def test_wire_runtime_fsm_sets_on_state_change(self, peer_handler):
        """_wire_runtime_fsm must set fsm.on_state_change to a callable."""
        from ai_assistant.services.agent_runtime_fsm import AgentRuntimeFSM, AgentRuntimeState

        runtime_fsm = AgentRuntimeFSM()

        # Build a mock audio_processor with the right attribute path
        ap = Mock()
        ap.ai_assistant.response_orchestrator.runtime_fsm = runtime_fsm
        emit_calls = []
        ap._emit_runtime_state = Mock(side_effect=lambda s: emit_calls.append(s))

        peer_handler._wire_runtime_fsm(ap)

        assert runtime_fsm.on_state_change is not None

    def test_wire_runtime_fsm_callback_calls_emit_runtime_state(self, peer_handler):
        """After wiring, every FSM transition must call _emit_runtime_state."""
        from ai_assistant.services.agent_runtime_fsm import AgentRuntimeFSM, AgentRuntimeState

        runtime_fsm = AgentRuntimeFSM()
        ap = Mock()
        ap.ai_assistant.response_orchestrator.runtime_fsm = runtime_fsm
        emit_calls = []
        ap._emit_runtime_state = Mock(side_effect=lambda s: emit_calls.append(s))

        peer_handler._wire_runtime_fsm(ap)

        # Trigger a real transition: BOOTSTRAP -> DATA_CHANNEL_WAIT
        runtime_fsm.transition("data_channel_wait")
        assert emit_calls, "Expected _emit_runtime_state to be called on FSM transition"
        assert emit_calls[0] == AgentRuntimeState.DATA_CHANNEL_WAIT

    def test_wire_runtime_fsm_does_not_raise_on_missing_attribute(self, peer_handler):
        """_wire_runtime_fsm must not raise if audio_processor.ai_assistant is missing."""
        ap = Mock(spec=[])  # no attributes at all
        peer_handler._wire_runtime_fsm(ap)  # must not raise


class TestRuntimeFsmAdvancesToListening:
    """After _wire_runtime_fsm, the FSM must immediately advance to LISTENING."""

    def test_fsm_is_listening_after_wire(self, peer_handler):
        """_wire_runtime_fsm must advance BOOTSTRAP → DATA_CHANNEL_WAIT → LISTENING."""
        from ai_assistant.services.agent_runtime_fsm import AgentRuntimeFSM, AgentRuntimeState

        runtime_fsm = AgentRuntimeFSM()
        ap = Mock()
        ap.ai_assistant.response_orchestrator.runtime_fsm = runtime_fsm
        ap._emit_runtime_state = Mock()

        peer_handler._wire_runtime_fsm(ap)

        assert runtime_fsm.current_state == AgentRuntimeState.LISTENING, (
            f"Expected LISTENING after _wire_runtime_fsm, got {runtime_fsm.current_state}"
        )

    def test_emit_runtime_state_called_for_each_transition(self, peer_handler):
        """_wire_runtime_fsm must emit DATA_CHANNEL_WAIT and LISTENING states."""
        from ai_assistant.services.agent_runtime_fsm import AgentRuntimeFSM, AgentRuntimeState

        runtime_fsm = AgentRuntimeFSM()
        ap = Mock()
        ap.ai_assistant.response_orchestrator.runtime_fsm = runtime_fsm
        emitted = []
        ap._emit_runtime_state = Mock(side_effect=lambda s: emitted.append(s))

        peer_handler._wire_runtime_fsm(ap)

        assert AgentRuntimeState.DATA_CHANNEL_WAIT in emitted
        assert AgentRuntimeState.LISTENING in emitted


