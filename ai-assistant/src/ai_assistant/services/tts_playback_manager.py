"""
TTS Playback Service
Manages text-to-speech playback with sentence processing and ordering.
"""
import asyncio
import logging
import re
from dataclasses import dataclass, field
from collections.abc import AsyncIterator
from typing import Optional, Callable
from collections.abc import Awaitable

from ..services.text_to_speech_service import TextToSpeechService

logger = logging.getLogger(__name__)


@dataclass
class SentenceChunk:
    """Represents a sentence chunk with order information."""
    order: int
    text: str
    audio_queue: asyncio.Queue = field(default_factory=asyncio.Queue)


class SentenceParser:
    """Parses and manages sentence boundaries."""

    # Sentence-ending punctuation pattern
    SENTENCE_END_PATTERN = re.compile(r'([.!?]+(?:\s+|$))')

    # Short sentence threshold
    MIN_SENTENCE_LENGTH = 15

    # B4: Hard char-length fallback — if no punctuation appears within this
    # many characters, force-split at the nearest space to prevent the audio
    # pipeline from being blocked indefinitely by a very long non-punctuated block.
    MAX_UNPUNCTUATED_LENGTH = 200

    @classmethod
    def split_into_sentences(cls, text: str) -> list[str]:
        """
        Split text into sentences.

        Args:
            text: Text to split

        Returns:
            List of sentences
        """
        if not text:
            return []

        # Split by sentence-ending punctuation
        parts = cls.SENTENCE_END_PATTERN.split(text)

        # Reconstruct sentences with their punctuation
        sentences = []
        for i in range(0, len(parts) - 1, 2):
            sentence = parts[i].strip()
            if i + 1 < len(parts):
                sentence += parts[i + 1].strip()
            if sentence:
                sentences.append(sentence)

        # Add remaining text if any
        if parts and len(parts) % 2 == 1:
            last_part = parts[-1].strip()
            if last_part:
                sentences.append(last_part)

        return sentences

    @classmethod
    def merge_short_sentences(cls, sentences: list[str]) -> list[str]:
        """
        Merge sentences that are too short.

        Args:
            sentences: List of sentences

        Returns:
            List of merged sentences
        """
        if not sentences:
            return []

        merged = []
        current = ""

        for sentence in sentences:
            if current:
                combined = f"{current} {sentence}"
            else:
                combined = sentence

            # If combined is long enough or this is the last sentence, add it
            if len(combined) >= cls.MIN_SENTENCE_LENGTH or sentence == sentences[-1]:
                merged.append(combined)
                current = ""
            else:
                current = combined

        # Add any remaining text
        if current:
            if merged:
                merged[-1] += f" {current}"
            else:
                merged.append(current)

        return merged


class TTSPlaybackManager:
    """Manages TTS playback with ordered sentence processing."""

    def __init__(
        self,
        tts_service: TextToSpeechService,
        on_audio_ready: Callable[[bytes, bool, bool], Awaitable[None]]
    ):
        """
        Initialize TTS playback manager.

        Args:
            tts_service: Text-to-speech service instance
            on_audio_ready: Callback for when audio is ready to play
        """
        self.tts_service = tts_service
        self.on_audio_ready: Callable[[bytes, bool, bool], Awaitable[None]] = on_audio_ready
        
        self._chunks: dict[int, SentenceChunk] = {}
        self._next_to_play = 0
        self._lock = asyncio.Lock()
        self._chunk_registered = asyncio.Event()
        self._processing = False
        self._interrupted = False
        self._total_audio_bytes = 0
        self._total_sentences = 0
        self._llm_stream_complete = False
        self._first_audio_at: float = 0.0  # monotonic time when first audio byte was forwarded
        self._synthesis_tasks: list[asyncio.Task] = []
    
    async def process_llm_stream(
        self,
        llm_stream: AsyncIterator[str],
        sentence_parser: Optional[SentenceParser] = None
    ) -> tuple[int, float]:
        """
        Process LLM stream: accumulate sentences, synthesize TTS, and play in order.

        Args:
            llm_stream: Async iterator of LLM output chunks
            sentence_parser: Optional sentence parser (uses default if None)
        """
        if sentence_parser is None:
            sentence_parser = SentenceParser()

        self._processing = True
        self._interrupted = False
        self._chunks.clear()
        self._next_to_play = 0
        self._total_audio_bytes = 0
        self._total_sentences = 0
        self._llm_stream_complete = False
        self._chunk_registered.clear()
        self._first_audio_at = 0.0
        self._synthesis_tasks = []

        # Wrap the audio callback to capture the timestamp of the very first
        # audio byte forwarded.  This lets _monitor_playback_completion
        # subtract actual elapsed playback time rather than guessing.
        _original_on_audio = self.on_audio_ready

        async def _timestamped_audio(*args, **kwargs):
            if self._first_audio_at == 0.0:
                self._first_audio_at = asyncio.get_event_loop().time()
            await _original_on_audio(*args, **kwargs)

        self.on_audio_ready = _timestamped_audio

        accumulated_text = ""
        sentence_order = 0

        playback_task = asyncio.create_task(self._playback_loop())

        try:
            async for chunk in llm_stream:
                if self._interrupted:
                    logger.info("TTS playback interrupted")
                    break

                accumulated_text += chunk

                # Check if we have complete sentences
                sentences = sentence_parser.split_into_sentences(accumulated_text)

                if len(sentences) > 1:
                    # Create TTS tasks for all complete sentences (all but the last)
                    for sentence in sentences[:-1]:
                        await self._synthesize_and_queue(sentence, sentence_order)
                        sentence_order += 1

                    # Keep the incomplete last sentence
                    accumulated_text = sentences[-1]

                # B4: Hard character-length fallback — force-split at the nearest
                # space when no punctuation appears within MAX_UNPUNCTUATED_LENGTH
                # chars to prevent the audio pipeline from stalling indefinitely.
                elif len(accumulated_text) >= sentence_parser.MAX_UNPUNCTUATED_LENGTH:
                    split_pos = accumulated_text.rfind(' ')
                    if split_pos > 0:
                        force_chunk = accumulated_text[:split_pos].strip()
                        accumulated_text = accumulated_text[split_pos:].strip()
                    else:
                        # No space found — split at the boundary as a last resort
                        force_chunk = accumulated_text
                        accumulated_text = ""
                    if force_chunk:
                        logger.debug(
                            "B4: forced TTS split at %d chars (no punctuation): '%s...'",
                            len(force_chunk), force_chunk[:40],
                        )
                        await self._synthesize_and_queue(force_chunk, sentence_order)
                        sentence_order += 1

            # Process any remaining text
            if accumulated_text.strip() and not self._interrupted:
                await self._synthesize_and_queue(accumulated_text.strip(), sentence_order)
                sentence_order += 1

            self._total_sentences = sentence_order
            self._llm_stream_complete = True
            self._chunk_registered.set()  # wake up playback loop for completion check

            if not self._interrupted:
                await playback_task
            else:
                playback_task.cancel()
                try:
                    await playback_task
                except asyncio.CancelledError:
                    pass

        except Exception as e:
            logger.error("Error in TTS playback: %s", e, exc_info=True)
            playback_task.cancel()
            try:
                await playback_task
            except asyncio.CancelledError:
                pass
            raise
        finally:
            # Cancel any synthesis tasks still running (occurs on interrupt or error).
            # This prevents stale gRPC streams from holding the TTS concurrency slot
            # and stops them from retaining a reference to this manager after it is done.
            tasks = list(self._synthesis_tasks)
            for t in tasks:
                if not t.done():
                    t.cancel()
            if tasks:
                # Await all tasks so their CancelledError cleanup runs (e.g. the
                # queue sentinel put in _synthesize_chunk that unblocks the playback
                # loop) before we reset state.  We need synthesis tasks to fully
                # finish even when this coroutine itself is being cancelled.
                # asyncio.shield() prevents the inner gather from being cancelled,
                # but the outer coroutine still receives CancelledError at the await.
                # Catching it and awaiting the (now unshielded) task ensures all
                # tasks finish before cancellation propagates.
                cleanup = asyncio.ensure_future(
                    asyncio.gather(*tasks, return_exceptions=True)
                )
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    # On Python 3.14, catching CancelledError does not clear
                    # the cancellation state of the current task, so an
                    # unshielded `await cleanup` would re-raise immediately and
                    # skip synthesis task cleanup.  Call uncancel() to
                    # temporarily clear the cancellation flag so we can
                    # reliably drain all synthesis tasks, then re-raise.
                    current_task = asyncio.current_task()
                    if current_task is not None:
                        current_task.uncancel()
                    await cleanup
                    raise
            self._synthesis_tasks = []
            self._processing = False
            self.on_audio_ready = _original_on_audio

        return (self._total_audio_bytes, self._first_audio_at)
    
    async def _synthesize_and_queue(self, text: str, order: int) -> None:
        """
        Synthesize text to audio and queue for playback.

        Args:
            text: Text to synthesize
            order: Playback order
        """
        logger.info("Synthesizing sentence %s: %s...", order, text[:50])
        
        # Register chunk and start synthesis task
        chunk = SentenceChunk(order=order, text=text)
        async with self._lock:
            self._chunks[order] = chunk
        self._chunk_registered.set()

        task = asyncio.create_task(self._synthesize_chunk(order, text))
        self._synthesis_tasks.append(task)
        task.add_done_callback(
            lambda t, tasks=self._synthesis_tasks: tasks.remove(t) if t in tasks else None
        )

    async def _synthesize_chunk(self, order: int, text: str) -> None:
        """
        Synthesize audio and push bytes into the chunk's queue as they arrive.
        Puts None as a sentinel when synthesis is complete or on error.

        Args:
            order: Chunk order
            text: Text to synthesize
        """
        chunk = self._chunks.get(order)
        if not chunk:
            return
        try:
            async for audio_bytes in self.tts_service.synthesize_stream(text):
                if audio_bytes:
                    self._total_audio_bytes += len(audio_bytes)
                    await chunk.audio_queue.put(audio_bytes)
            logger.info("Synthesis complete for chunk %s", order)
        except Exception as e:
            logger.error("Error synthesizing chunk %s: %s", order, e, exc_info=True)
        finally:
            await chunk.audio_queue.put(None)  # sentinel: signals end of this chunk's audio

    async def _playback_loop(self) -> None:
        """Play chunks in order, forwarding bytes to on_audio_ready as synthesis produces them."""
        order = 0
        while not self._interrupted:
            # Wait until the next chunk has been registered
            while True:
                async with self._lock:
                    # Clear the event *inside* the lock so we cannot miss a
                    # notification that fires between releasing the lock and
                    # calling wait() below (classic check-then-act race).
                    self._chunk_registered.clear()
                    chunk = self._chunks.get(order)
                if chunk is not None:
                    break
                if self._llm_stream_complete and order >= self._total_sentences:
                    return
                try:
                    await asyncio.wait_for(self._chunk_registered.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    if self._interrupted:
                        return

            # Stream bytes to output as synthesis produces them.
            # Track first/last position so on_audio_ready can apply fades only at
            # sentence boundaries and not on every intermediate streaming chunk.
            prev_bytes: Optional[bytes] = None
            is_first = True
            while not self._interrupted:
                try:
                    audio_bytes = await asyncio.wait_for(chunk.audio_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                if audio_bytes is None:  # sentinel: synthesis for this sentence is done
                    # Flush the last buffered chunk as the sentence-final one
                    if prev_bytes is not None:
                        await self.on_audio_ready(prev_bytes, is_first, True)
                    break
                # Send the previously held chunk (now known not to be last)
                if prev_bytes is not None:
                    await self.on_audio_ready(prev_bytes, is_first, False)
                    is_first = False
                prev_bytes = audio_bytes

            logger.info("Finished playing chunk %s", order)
            async with self._lock:
                self._chunks.pop(order, None)
            self._next_to_play = order + 1
            order += 1

            if self._llm_stream_complete and order >= self._total_sentences:
                return

    def interrupt(self) -> None:
        """Interrupt current playback."""
        if self._processing:
            logger.info("Interrupting TTS playback")
            self._interrupted = True

    def is_processing(self) -> bool:
        """Check if currently processing playback."""
        return self._processing

    def is_interrupted(self) -> bool:
        """Check if playback was interrupted."""
        return self._interrupted

    async def clear(self) -> None:
        """Clear all pending chunks."""
        async with self._lock:
            self._chunks.clear()
            self._next_to_play = 0
