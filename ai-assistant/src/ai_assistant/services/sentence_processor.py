"""
Sentence Processor
Handles sentence extraction and TTS processing from LLM stream.
"""
import asyncio
import logging
import re
from typing import AsyncIterator, Callable
import numpy as np

from .audio_utils import AudioFadeProcessor

logger = logging.getLogger(__name__)


class SentenceProcessor:
    """Processes sentences from LLM stream and coordinates TTS playback."""

    def __init__(self, tts_service, output_track, interrupt_handler):
        """
        Initialize sentence processor.
        
        Args:
            tts_service: Text-to-speech service
            output_track: Audio output track
            interrupt_handler: Interrupt handler for cancellation
        """
        self.tts_service = tts_service
        self.output_track = output_track
        self.interrupt_handler = interrupt_handler

    async def process_llm_stream(
        self,
        llm_stream: AsyncIterator[str]
    ) -> tuple[str, list]:
        """
        Process LLM stream, extract sentences, and generate TTS.
        
        Args:
            llm_stream: Async iterator of LLM chunks
            
        Returns:
            Tuple of (full_llm_response, list_of_tts_tasks)
        """
        sentence_buffer = ""
        sentence_num = 0
        tts_tasks = []
        llm_parts = []

        # Mechanism for ordered sentence playback
        sentence_events = {}
        playback_lock = asyncio.Lock()

        async for llm_chunk in llm_stream:
            if not llm_chunk:
                continue

            llm_parts.append(llm_chunk)
            sentence_buffer += llm_chunk

            # Extract and process complete sentences
            extracted_sentences = self._extract_sentences(sentence_buffer)
            sentence_buffer = extracted_sentences['remaining_buffer']

            for sentence in extracted_sentences['sentences']:
                sentence_num += 1
                task = asyncio.create_task(
                    self._process_sentence_to_audio(
                        sentence,
                        sentence_num,
                        sentence_events,
                        playback_lock
                    )
                )
                tts_tasks.append(task)
                self.interrupt_handler.add_tts_task(task)

        # Process any remaining text in buffer
        if sentence_buffer.strip():
            sentence_num += 1
            task = asyncio.create_task(
                self._process_sentence_to_audio(
                    sentence_buffer.strip(),
                    sentence_num,
                    sentence_events,
                    playback_lock
                )
            )
            tts_tasks.append(task)
            self.interrupt_handler.add_tts_task(task)

        full_response = "".join(llm_parts)
        return full_response, tts_tasks

    def _extract_sentences(self, buffer: str) -> dict:
        """
        Extract complete sentences from buffer.
        
        Args:
            buffer: Text buffer to process
            
        Returns:
            Dict with 'sentences' list and 'remaining_buffer'
        """
        sentence_end_pattern = r'([.!?][\s\n]+|:\n)'
        sentences = []

        while True:
            matches = list(re.finditer(sentence_end_pattern, buffer))
            if not matches:
                # Check if buffer is getting too long
                if len(buffer.split()) >= 20:
                    return self._force_break_at_punctuation(buffer)
                break

            # Extract sentences at boundaries
            last_end = 0
            extracted = []
            for match in matches:
                end_pos = match.end()
                sentence = buffer[last_end:end_pos].strip()
                if sentence:
                    extracted.append(sentence)
                last_end = end_pos

            buffer = buffer[last_end:]

            # Merge short sentences (< 3 words)
            merged = self._merge_short_sentences(extracted)
            sentences.extend(merged)

        return {
            'sentences': sentences,
            'remaining_buffer': buffer
        }

    def _merge_short_sentences(self, sentences: list) -> list:
        """Merge sentences that are too short (< 3 words)."""
        merged_sentences = []
        i = 0

        while i < len(sentences):
            s = sentences[i]
            word_count = len(s.split())

            if word_count >= 3:
                merged_sentences.append(s)
                i += 1
            else:
                # Merge with following sentences
                merged = s
                i += 1
                while word_count < 3 and i < len(sentences):
                    merged = (merged + " " + sentences[i]).strip()
                    word_count = len(merged.split())
                    i += 1
                merged_sentences.append(merged)

        return merged_sentences

    def _force_break_at_punctuation(self, buffer: str) -> dict:
        """Force sentence break at punctuation when buffer is too long."""
        break_pattern = r'([,;—–-]\s+)'
        break_match = re.search(break_pattern, buffer)

        if break_match:
            end_pos = break_match.end()
            sentence = buffer[:end_pos].strip()
            remaining = buffer[end_pos:]
            return {
                'sentences': [sentence] if sentence else [],
                'remaining_buffer': remaining
            }

        return {'sentences': [], 'remaining_buffer': buffer}

    async def _process_sentence_to_audio(
        self,
        sentence: str,
        sentence_num: int,
        sentence_events: dict,
        playback_lock: asyncio.Lock
    ):
        """Process a sentence through TTS and queue audio in order."""
        try:
            # Check for interrupt
            if self.interrupt_handler.is_interrupted():
                logger.info(f"Sentence {sentence_num} skipped due to interrupt")
                return

            logger.info(f"TTS for sentence {sentence_num}: '{sentence}'")

            # Create event for ordered playback
            my_event = asyncio.Event()
            sentence_events[sentence_num] = my_event

            # First sentence can play immediately
            if sentence_num == 1:
                my_event.set()

            # Generate TTS audio
            audio_chunks = []
            async for audio_chunk in self.tts_service.synthesize_speech(sentence):
                if self.interrupt_handler.is_interrupted():
                    logger.info(f"Sentence {sentence_num} interrupted during TTS")
                    return
                if audio_chunk:
                    audio_chunks.append(audio_chunk)

            logger.debug(f"TTS sentence {sentence_num}: {len(audio_chunks)} chunks, waiting for turn")

            # Check interrupt before waiting
            if self.interrupt_handler.is_interrupted():
                logger.info(f"Sentence {sentence_num} interrupted before playback")
                return

            # Wait for our turn
            await my_event.wait()

            # Final interrupt check
            if self.interrupt_handler.is_interrupted():
                logger.info(f"Sentence {sentence_num} interrupted at playback")
                return

            # Queue audio atomically
            await self._queue_audio_with_fades(
                audio_chunks,
                sentence_num,
                playback_lock
            )

            # Signal next sentence
            async with playback_lock:
                next_sentence = sentence_num + 1
                if next_sentence in sentence_events:
                    sentence_events[next_sentence].set()

        except Exception as e:
            logger.error(f"Error in TTS for sentence {sentence_num}: {e}", exc_info=True)
            # Signal next sentence on error to prevent deadlock
            async with playback_lock:
                next_sentence = sentence_num + 1
                if next_sentence in sentence_events:
                    sentence_events[next_sentence].set()

    async def _queue_audio_with_fades(
        self,
        audio_chunks: list,
        sentence_num: int,
        playback_lock: asyncio.Lock
    ):
        """Queue audio chunks with fade effects applied."""
        async with playback_lock:
            logger.info(f"Playing sentence {sentence_num} ({len(audio_chunks)} chunks)")

            # Combine all chunks
            combined_audio = b''.join(audio_chunks)
            audio_samples = np.frombuffer(combined_audio, dtype=np.int16).copy()

            # Apply fades
            is_first = (sentence_num == 1)
            audio_samples = AudioFadeProcessor.apply_fades(audio_samples, is_first)

            # Queue the processed audio
            await self.output_track.queue_audio(audio_samples.tobytes())
            logger.debug(f"Sentence {sentence_num} playback complete")
