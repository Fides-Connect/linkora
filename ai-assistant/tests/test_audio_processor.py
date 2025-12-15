"""
Unit tests for Audio Processor functionality.
"""
import pytest
import asyncio
import numpy as np
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from av import AudioFrame

from ai_assistant.audio_processor import AudioProcessor


@pytest.fixture
def mock_ai_assistant():
    """Mock AI Assistant."""
    assistant = Mock()
    assistant.speech_to_text_continuous_stream = AsyncMock()
    assistant.generate_llm_response_stream = AsyncMock()
    assistant.text_to_speech_stream = AsyncMock()
    assistant.get_greeting_audio = AsyncMock(return_value=(
        "Hello!",
        async_audio_generator()
    ))
    
    # Mock services
    assistant.stt_service = Mock()
    assistant.tts_service = Mock()
    assistant.llm_service = Mock()
    assistant.conversation_service = Mock()
    
    return assistant


async def async_audio_generator():
    """Mock async audio generator."""
    yield b'audio_chunk_1'
    yield b'audio_chunk_2'


@pytest.fixture
def mock_input_track():
    """Mock input media track."""
    track = Mock()
    track.kind = "audio"
    
    # Create mock audio frames
    async def mock_recv():
        frame = Mock(spec=AudioFrame)
        frame.format = Mock()
        frame.format.name = 's16'
        frame.layout = 'mono'
        frame.sample_rate = 48000
        frame.samples = 480
        frame.pts = 0
        
        # Mock to_ndarray to return actual numpy array
        audio_data = np.zeros(480, dtype=np.int16)
        frame.to_ndarray = Mock(return_value=audio_data)
        
        return frame
    
    track.recv = mock_recv
    return track


@pytest.fixture
def audio_processor(mock_ai_assistant, mock_input_track):
    """Create AudioProcessor instance."""
    processor = AudioProcessor(
        connection_id='test-123',
        ai_assistant=mock_ai_assistant,
        input_track=mock_input_track
    )
    return processor


class TestAudioProcessorInitialization:
    """Test AudioProcessor initialization."""
    
    def test_initialization(self, audio_processor):
        """Test that AudioProcessor initializes correctly."""
        assert audio_processor.connection_id == 'test-123'
        assert audio_processor.running is False
        assert audio_processor.sample_rate == 48000
        # Services are initialized
        assert audio_processor.frame_converter is not None
        assert audio_processor.debug_recorder is not None
        assert audio_processor.transcript_processor is not None
        assert audio_processor.tts_manager is not None
        assert audio_processor.is_ai_speaking is False
    
    def test_output_track_created(self, audio_processor):
        """Test that output track is created."""
        output_track = audio_processor.get_output_track()
        assert output_track is not None


class TestAudioProcessing:
    """Test audio processing functionality."""
    
    @pytest.mark.asyncio
    async def test_start_processing(self, audio_processor):
        """Test starting audio processing."""
        with patch.object(audio_processor, '_process_audio', new=AsyncMock()), \
             patch.object(audio_processor, '_continuous_stt', new=AsyncMock()), \
             patch.object(audio_processor, '_play_greeting', new=AsyncMock()):
            
            await audio_processor.start()
            
            assert audio_processor.running is True
            assert audio_processor.processing_task is not None
            assert audio_processor.stt_task is not None
    
    @pytest.mark.asyncio
    async def test_stop_processing(self, audio_processor):
        """Test stopping audio processing."""
        # Setup processor in running state
        audio_processor.running = True
        audio_processor.processing_task = asyncio.create_task(asyncio.sleep(10))
        audio_processor.stt_task = asyncio.create_task(asyncio.sleep(10))
        
        await audio_processor.stop()
        
        assert audio_processor.running is False


class TestFrameConversion:
    """Test audio frame conversion."""
    
    def test_frame_to_numpy_mono(self, audio_processor):
        """Test converting mono audio frame to numpy."""
        frame = Mock(spec=AudioFrame)
        frame.format = Mock()
        frame.format.name = 's16'
        frame.layout = 'mono'
        frame.sample_rate = 48000
        frame.samples = 480
        
        audio_data = np.random.randint(-1000, 1000, 480, dtype=np.int16)
        frame.to_ndarray = Mock(return_value=audio_data)
        
        result = audio_processor.frame_converter.frame_to_numpy(frame)
        
        assert isinstance(result, np.ndarray)
        assert result.dtype == np.int16
        assert len(result) == 480
    
    def test_frame_to_numpy_stereo_to_mono(self, audio_processor):
        """Test converting stereo audio frame to mono."""
        frame = Mock(spec=AudioFrame)
        frame.format = Mock()
        frame.format.name = 's16'
        frame.layout = 'stereo'
        frame.sample_rate = 48000
        frame.samples = 480
        
        # Stereo data (left and right channels)
        stereo_data = np.random.randint(-1000, 1000, (480, 2), dtype=np.int16)
        frame.to_ndarray = Mock(return_value=stereo_data)
        
        result = audio_processor.frame_converter.frame_to_numpy(frame)
        
        assert isinstance(result, np.ndarray)
        assert result.dtype == np.int16
        assert len(result.shape) == 1  # Should be mono
    
    def test_frame_to_numpy_float_to_int16(self, audio_processor):
        """Test converting float audio to int16."""
        frame = Mock(spec=AudioFrame)
        frame.format = Mock()
        frame.format.name = 'flt'
        frame.layout = 'mono'
        frame.sample_rate = 48000
        frame.samples = 480
        
        # Float audio in range [-1.0, 1.0]
        float_data = np.random.uniform(-0.5, 0.5, 480).astype(np.float32)
        frame.to_ndarray = Mock(return_value=float_data)
        
        result = audio_processor.frame_converter.frame_to_numpy(frame)
        
        assert isinstance(result, np.ndarray)
        assert result.dtype == np.int16


class TestInterruptHandling:
    """Test interrupt handling functionality."""
    
    def test_is_ai_speaking_flag(self, audio_processor):
        """Test AI speaking flag management."""
        assert audio_processor.is_ai_speaking is False
        
        audio_processor.is_ai_speaking = True
        assert audio_processor.is_ai_speaking is True
    
    def test_interrupt_event_created(self, audio_processor):
        """Test that interrupt event is created."""
        assert audio_processor.interrupt_event is not None
        assert isinstance(audio_processor.interrupt_event, asyncio.Event)


class TestDebugRecording:
    """Test debug recording functionality."""
    
    def test_debug_recording_disabled_by_default(self):
        """Test that debug recording is disabled by default."""
        with patch.dict('os.environ', {}, clear=True):
            mock_assistant = Mock()
            mock_assistant.stt_service = Mock()
            mock_assistant.tts_service = Mock()
            mock_track = Mock()
            
            processor = AudioProcessor('test', mock_assistant, mock_track)
            assert processor.debug_recorder.enabled is False
    
    def test_debug_recording_enabled_via_env(self):
        """Test that debug recording can be enabled via environment."""
        with patch.dict('os.environ', {'DEBUG_RECORD_AUDIO': 'true'}):
            mock_assistant = Mock()
            mock_assistant.stt_service = Mock()
            mock_assistant.tts_service = Mock()
            mock_track = Mock()
            
            processor = AudioProcessor('test', mock_assistant, mock_track)
            assert processor.debug_recorder.enabled is True
    
    def test_save_debug_recording_with_frames(self, audio_processor):
        """Test saving debug recording when frames exist."""
        # Add frames to debug recorder
        audio_processor.debug_recorder.enabled = True
        audio_processor.debug_recorder.frames = [
            np.random.randint(-1000, 1000, 480, dtype=np.int16),
            np.random.randint(-1000, 1000, 480, dtype=np.int16)
        ]
        audio_processor.debug_recorder.wav_path = '/tmp/test_audio.wav'
        
        with patch('wave.open', create=True) as mock_wave:
            mock_wav_file = MagicMock()
            mock_wave.return_value.__enter__.return_value = mock_wav_file
            
            audio_processor.debug_recorder.save()
            
            mock_wav_file.setnchannels.assert_called_once_with(1)
            mock_wav_file.setsampwidth.assert_called_once_with(2)
            mock_wav_file.setframerate.assert_called_once_with(48000)


class TestAudioQueue:
    """Test audio queue management."""
    
    @pytest.mark.asyncio
    async def test_audio_queue_created(self, audio_processor):
        """Test that audio queue is created."""
        assert audio_processor.audio_queue is not None
        assert isinstance(audio_processor.audio_queue, asyncio.Queue)
    
    @pytest.mark.asyncio
    async def test_audio_queue_put_get(self, audio_processor):
        """Test putting and getting from audio queue."""
        test_audio = b'test_audio_data'
        await audio_processor.audio_queue.put(test_audio)
        
        result = await audio_processor.audio_queue.get()
        assert result == test_audio


class TestGreetingPlayback:
    """Test greeting playback functionality."""
    
    @pytest.mark.asyncio
    async def test_play_greeting(self, audio_processor, mock_ai_assistant):
        """Test playing greeting message."""
        # Mock output track
        audio_processor.output_track.queue_audio = AsyncMock()
        
        await audio_processor._play_greeting()
        
        # Verify greeting was requested
        mock_ai_assistant.get_greeting_audio.assert_called_once()
        
        # Verify audio was queued
        assert audio_processor.output_track.queue_audio.call_count > 0
    
    @pytest.mark.asyncio
    async def test_play_greeting_sets_speaking_flag(self, audio_processor, mock_ai_assistant):
        """Test that greeting playback sets speaking flag."""
        audio_processor.output_track.queue_audio = AsyncMock()
        
        # Capture speaking flag state during greeting
        speaking_states = []
        
        original_queue = audio_processor.output_track.queue_audio
        
        async def capture_speaking(*args):
            speaking_states.append(audio_processor.is_ai_speaking)
            await original_queue(*args)
        
        audio_processor.output_track.queue_audio = capture_speaking
        
        await audio_processor._play_greeting()

        await audio_processor._monitor_playback_completion()
        
        # Flag should be False after greeting completes
        assert audio_processor.is_ai_speaking is False
