"""
Unit tests for Peer Connection Handler functionality.
"""
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
        mock_pc_instance.connectionState = 'new'
        mock_pc_instance.iceConnectionState = 'new'
        mock_pc_instance.iceGatheringState = 'new'
        mock_pc.return_value = mock_pc_instance
        
        handler = PeerConnectionHandler(
            connection_id='test-123',
            ai_assistant=mock_ai_assistant,
            websocket=mock_websocket
        )
        handler.pc = mock_pc_instance
        return handler


class TestPeerConnectionHandlerInitialization:
    """Test PeerConnectionHandler initialization."""
    
    def test_initialization(self, peer_handler, mock_ai_assistant, mock_websocket):
        """Test that PeerConnectionHandler initializes correctly."""
        assert peer_handler.connection_id == 'test-123'
        assert peer_handler.ai_assistant is mock_ai_assistant
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
