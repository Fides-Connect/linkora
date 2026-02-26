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
def audio_processor(mock_input_track):
    """Create AudioProcessor instance."""
    # Mock Google Cloud clients to avoid credential issues in tests
    with patch('ai_assistant.services.speech_to_text_service.SpeechAsyncClient'), \
         patch('ai_assistant.services.text_to_speech_service.TextToSpeechAsyncClient'):
        processor = AudioProcessor(
            connection_id='test-123',
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

    def test_firestore_service_injected_into_ai_assistant(self, audio_processor):
        """Regression: firestore_service must be non-None so Firestore tools can run.

        Covers the bug where _create_language_specific_assistant wired AIConversationService
        but forgot to set assistant.firestore_service, causing all Firestore-dependent tools
        to crash with AttributeError: 'NoneType' object has no attribute 'update_user'.
        """
        assert audio_processor.ai_assistant.firestore_service is not None


class TestAudioProcessing:
    """Test audio processing functionality."""
    
    @pytest.mark.asyncio
    async def test_start_processing(self, audio_processor):
        """Test starting audio processing."""
        with patch.object(audio_processor, '_process_audio', new=AsyncMock()), \
             patch.object(audio_processor, '_continuous_stt', new=AsyncMock()), \
             patch.object(audio_processor._session_starter, 'initialize', new=AsyncMock()):
            
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


class TestTrackReplacement:
    """Test input track replacement for mid-stream device switching."""
    
    @pytest.mark.asyncio
    async def test_replace_input_track(self, audio_processor, mock_input_track):
        """Test replacing input track during renegotiation."""
        # Mock _process_audio to prevent it from actually running
        with patch.object(audio_processor, '_process_audio', new=AsyncMock()) as mock_process:
            # Setup processor in running state
            audio_processor.running = True
            audio_processor.processing_task = asyncio.create_task(asyncio.sleep(0.1))
            
            # Create new mock track
            new_track = Mock()
            new_track.kind = "audio"
            new_track.id = "new-track-456"
            
            # Replace track
            await audio_processor.replace_input_track(new_track)
            
            # Verify track was replaced
            assert audio_processor.input_track == new_track
            assert audio_processor.input_track.id == "new-track-456"
            
            # Verify new processing task was created
            assert audio_processor.processing_task is not None
    
    @pytest.mark.asyncio
    async def test_replace_input_track_cancels_old_task(self, audio_processor):
        """Test that old processing task is cancelled during track replacement."""
        # Mock _process_audio to prevent it from actually running
        with patch.object(audio_processor, '_process_audio', new=AsyncMock()):
            # Setup processor with running task
            audio_processor.running = True
            old_task = asyncio.create_task(asyncio.sleep(0.1))
            audio_processor.processing_task = old_task
            
            # Create new mock track
            new_track = Mock()
            new_track.kind = "audio"
            new_track.id = "new-track-789"
            
            # Replace track
            await audio_processor.replace_input_track(new_track)
            
            # Verify old task was cancelled
            assert old_task.cancelled()
    
    @pytest.mark.asyncio
    async def test_replace_input_track_preserves_audio_queue(self, audio_processor):
        """Test that audio queue is preserved during track replacement to avoid audio loss."""
        # Mock _process_audio to prevent it from actually running
        with patch.object(audio_processor, '_process_audio', new=AsyncMock()):
            # Setup processor
            audio_processor.running = True
            audio_processor.processing_task = asyncio.create_task(asyncio.sleep(0.1))
            
            # Add items to audio queue
            await audio_processor.audio_queue.put(b'old_audio_1')
            await audio_processor.audio_queue.put(b'old_audio_2')
            assert audio_processor.audio_queue.qsize() == 2
            
            # Create new mock track
            new_track = Mock()
            new_track.kind = "audio"
            new_track.id = "new-track-preserve"
            
            # Replace track
            await audio_processor.replace_input_track(new_track)
            
            # Verify queue was NOT cleared - audio is preserved during transition
            assert audio_processor.audio_queue.qsize() == 2
    
    @pytest.mark.asyncio
    async def test_replace_input_track_restarts_processing(self, audio_processor):
        """Test that processing is restarted after track replacement."""
        # Mock _process_audio to prevent it from actually running
        with patch.object(audio_processor, '_process_audio', new=AsyncMock()) as mock_process:
            # Setup processor
            audio_processor.running = True
            old_task = asyncio.create_task(asyncio.sleep(0.1))
            audio_processor.processing_task = old_task
            
            # Create new mock track
            new_track = Mock()
            new_track.kind = "audio"
            new_track.id = "new-track-restart"
            
            # Replace track
            await audio_processor.replace_input_track(new_track)
            
            # Give a moment for the task to be created
            await asyncio.sleep(0.01)
            
            # Verify new processing task was created and is different from old one
            assert audio_processor.processing_task is not None
            assert audio_processor.processing_task != old_task
            # Verify old task was cancelled
            assert old_task.cancelled()


class TestDebugRecording:
    """Test debug recording functionality."""
    
    def test_debug_recording_disabled_by_default(self):
        """Test that debug recording is disabled by default."""
        with patch.dict('os.environ', {'DEBUG_RECORD_AUDIO': 'false'}), \
             patch('ai_assistant.services.speech_to_text_service.SpeechAsyncClient'), \
             patch('ai_assistant.services.text_to_speech_service.TextToSpeechAsyncClient'):
            mock_track = Mock()
            
            processor = AudioProcessor('test', mock_track)
            assert processor.debug_recorder.enabled is False
    
    def test_debug_recording_enabled_via_env(self):
        """Test that debug recording can be enabled via environment."""
        with patch.dict('os.environ', {'DEBUG_RECORD_AUDIO': 'true'}), \
             patch('ai_assistant.services.speech_to_text_service.SpeechAsyncClient'), \
             patch('ai_assistant.services.text_to_speech_service.TextToSpeechAsyncClient'):
            mock_track = Mock()
            
            processor = AudioProcessor('test', mock_track)
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



class TestTranscriptCallback:
    """Test on_transcript_final composability hook."""

    def test_on_transcript_final_is_initially_none(self, audio_processor):
        assert audio_processor.on_transcript_final is None

    def test_on_transcript_final_can_be_set(self, audio_processor):
        async def my_callback(text: str):
            pass

        audio_processor.on_transcript_final = my_callback
        assert audio_processor.on_transcript_final is my_callback

    @pytest.mark.asyncio
    async def test_on_transcript_final_callback_used_when_set(self, audio_processor):
        """When on_transcript_final is set, _continuous_stt calls it for final transcripts."""
        called_with = []

        async def capture(text: str):
            called_with.append(text)

        audio_processor.on_transcript_final = capture

        # Simulate one STT cycle producing a final transcript
        async def fake_audio_stream(_):
            yield "hello world", True  # (transcript, is_final)

        audio_processor.transcript_processor.process_audio_stream = Mock(
            return_value=fake_audio_stream(None)
        )
        audio_processor.running = True
        stt_task = asyncio.create_task(audio_processor._continuous_stt())
        await asyncio.sleep(0.05)
        audio_processor.running = False
        stt_task.cancel()
        try:
            await stt_task
        except asyncio.CancelledError:
            pass

        assert called_with == ["hello world"]

    @pytest.mark.asyncio
    async def test_fallback_to_process_final_transcript_when_callback_is_none(
        self, audio_processor
    ):
        """When on_transcript_final is None, _continuous_stt falls back to _process_final_transcript."""
        audio_processor.on_transcript_final = None

        pft_called = []

        async def fake_pft(text: str):
            pft_called.append(text)

        async def fake_audio_stream(_):
            yield "fallback text", True

        audio_processor.transcript_processor.process_audio_stream = Mock(
            return_value=fake_audio_stream(None)
        )
        audio_processor.running = True
        with patch.object(audio_processor, "_process_final_transcript", side_effect=fake_pft):
            stt_task = asyncio.create_task(audio_processor._continuous_stt())
            await asyncio.sleep(0.05)
            audio_processor.running = False
            stt_task.cancel()
            try:
                await stt_task
            except asyncio.CancelledError:
                pass

        assert pft_called == ["fallback text"]


class TestRuntimeStateEmission:
    """Test _emit_runtime_state DataChannel notification."""

    def test_emit_runtime_state_sends_data_channel_message(self, audio_processor):
        from ai_assistant.services.agent_runtime_fsm import AgentRuntimeState

        dc = Mock()
        dc.readyState = "open"
        sent = []
        dc.send = Mock(side_effect=lambda m: sent.append(m))
        audio_processor.data_channel = dc

        audio_processor._emit_runtime_state(AgentRuntimeState.LISTENING)

        assert len(sent) == 1
        import json
        msg = json.loads(sent[0])
        assert msg["type"] == "runtime-state"
        assert msg["runtimeState"] == AgentRuntimeState.LISTENING.value

    def test_emit_runtime_state_no_data_channel_does_not_crash(self, audio_processor):
        from ai_assistant.services.agent_runtime_fsm import AgentRuntimeState

        audio_processor.data_channel = None
        # Must not raise
        audio_processor._emit_runtime_state(AgentRuntimeState.THINKING)


# ══════════════════════════════════════════════════════════════════════════════
# Voice-mode FINALIZE stage guard
# ══════════════════════════════════════════════════════════════════════════════

class TestVoiceFinalizeGuard:
    """
    When ConversationStage is FINALIZE, a voice final transcript received in
    _continuous_stt must send a 'please wait' message and NOT cancel the
    ongoing provider-search task.
    """

    @pytest.mark.asyncio
    async def test_voice_input_during_finalize_sends_busy_message(self, audio_processor):
        from ai_assistant.services.conversation_service import ConversationStage

        audio_processor.ai_assistant.conversation_service.get_current_stage = Mock(
            return_value=ConversationStage.FINALIZE
        )
        # Guard fires only while the search/presentation task is still running.
        running_task = asyncio.create_task(asyncio.sleep(999))
        audio_processor._response_task = running_task

        sent_messages = []

        with patch.object(
            audio_processor,
            "_send_chat_message",
            side_effect=lambda text, is_user, **kw: sent_messages.append(text),
        ):
            async def fake_audio_stream(_):
                yield "passende Anbieter bitte", True  # final transcript

            audio_processor.transcript_processor.process_audio_stream = Mock(
                return_value=fake_audio_stream(None)
            )
            audio_processor.running = True
            stt_task = asyncio.create_task(audio_processor._continuous_stt())
            await asyncio.sleep(0.05)
            audio_processor.running = False
            stt_task.cancel()
            try:
                await stt_task
            except asyncio.CancelledError:
                pass

        running_task.cancel()
        try:
            await running_task
        except asyncio.CancelledError:
            pass

        assert any(
            "such" in m.lower() or "search" in m.lower() or "moment" in m.lower()
            for m in sent_messages
        ), f"Expected a busy message, got: {sent_messages}"

    @pytest.mark.asyncio
    async def test_voice_input_during_finalize_does_not_cancel_task(self, audio_processor):
        from ai_assistant.services.conversation_service import ConversationStage

        audio_processor.ai_assistant.conversation_service.get_current_stage = Mock(
            return_value=ConversationStage.FINALIZE
        )

        never_done = asyncio.create_task(asyncio.sleep(999))
        audio_processor._response_task = never_done

        with patch.object(audio_processor, "_send_chat_message", new=Mock()):
            async def fake_audio_stream(_):
                yield "ich warte", True

            audio_processor.transcript_processor.process_audio_stream = Mock(
                return_value=fake_audio_stream(None)
            )
            audio_processor.running = True
            stt_task = asyncio.create_task(audio_processor._continuous_stt())
            await asyncio.sleep(0.05)
            audio_processor.running = False
            stt_task.cancel()
            try:
                await stt_task
            except asyncio.CancelledError:
                pass

        assert not never_done.cancelled(), (
            "Running provider-search task must NOT be cancelled during FINALIZE stage"
        )
        never_done.cancel()
        try:
            await never_done
        except asyncio.CancelledError:
            pass
