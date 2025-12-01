"""
Interrupt Handler Service
Manages AI speech interruption when user starts speaking.
"""
import asyncio
import logging
from typing import List

logger = logging.getLogger(__name__)


class InterruptHandler:
    """Handles interruption of AI speech when user starts speaking."""

    def __init__(self, output_track):
        """
        Initialize interrupt handler.
        
        Args:
            output_track: Audio output track to control
        """
        self.output_track = output_track
        self.is_ai_speaking = False
        self.interrupt_event = asyncio.Event()
        self.current_tts_tasks: List[asyncio.Task] = []

    def set_speaking(self, is_speaking: bool):
        """Set the AI speaking state."""
        self.is_ai_speaking = is_speaking

    def is_speaking(self) -> bool:
        """Check if AI is currently speaking."""
        return self.is_ai_speaking

    def add_tts_task(self, task: asyncio.Task):
        """Add a TTS task to track for interruption."""
        self.current_tts_tasks.append(task)

    def clear_tts_tasks(self):
        """Clear all tracked TTS tasks."""
        self.current_tts_tasks = []

    def is_interrupted(self) -> bool:
        """Check if interrupt has been triggered."""
        return self.interrupt_event.is_set()

    def clear_interrupt(self):
        """Clear the interrupt event."""
        self.interrupt_event.clear()

    async def trigger_interrupt(self):
        """Trigger an interrupt to stop ongoing AI speech."""
        logger.info("⚡ Triggering interrupt - cancelling ongoing TTS")

        # Set the interrupt event
        self.interrupt_event.set()

        # Cancel all ongoing TTS tasks
        for task in self.current_tts_tasks:
            if not task.done():
                task.cancel()

        # Clear the output audio queue immediately
        await self.output_track.clear_queue()

        # Reset state
        self.is_ai_speaking = False
        self.current_tts_tasks = []

        logger.info("✅ Interrupt complete - AI speech stopped")

    async def monitor_playback_completion(self):
        """Monitor audio queue and clear speaking flag when playback is done."""
        try:
            # Wait for audio to start queueing
            await asyncio.sleep(0.1)

            # Monitor queue size - when empty for a bit, we're done
            empty_count = 0
            while self.is_ai_speaking and not self.is_interrupted():
                queue_size = self.output_track.audio_queue.qsize()
                buffer_size = len(self.output_track._buffer)

                if queue_size == 0 and buffer_size == 0:
                    empty_count += 1
                    # Empty for 5 consecutive checks (100ms) means done
                    if empty_count >= 5:
                        logger.info("Audio playback completed - clearing speaking flag")
                        self.is_ai_speaking = False
                        break
                else:
                    empty_count = 0

                await asyncio.sleep(0.02)  # Check every 20ms

        except Exception as e:
            logger.error(f"Error in playback monitor: {e}", exc_info=True)
            self.is_ai_speaking = False
