"""
TTS Playback Service
Manages text-to-speech playback with sentence processing and ordering.
"""
import asyncio
import logging
import re
from dataclasses import dataclass
from collections.abc import AsyncIterator
from typing import Optional, Callable, Awaitable

from ..services.text_to_speech_service import TextToSpeechService

logger = logging.getLogger(__name__)


@dataclass
class SentenceChunk:
    """Represents a sentence chunk with order information."""
    order: int
    text: str
    audio_data: Optional[bytes] = None
    is_ready: bool = False


class SentenceParser:
    """Parses and manages sentence boundaries."""
    
    # Sentence-ending punctuation pattern
    SENTENCE_END_PATTERN = re.compile(r'([.!?]+(?:\s+|$))')
    
    # Short sentence threshold
    MIN_SENTENCE_LENGTH = 15
    
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
        on_audio_ready: Callable[[bytes], Awaitable[None]]
    ):
        """
        Initialize TTS playback manager.
        
        Args:
            tts_service: Text-to-speech service instance
            on_audio_ready: Callback for when audio is ready to play
        """
        self.tts_service = tts_service
        self.on_audio_ready = on_audio_ready
        
        self._chunks: dict[int, SentenceChunk] = {}
        self._next_to_play = 0
        self._lock = asyncio.Lock()
        self._processing = False
        self._interrupted = False
    
    async def process_llm_stream(
        self,
        llm_stream: AsyncIterator[str],
        sentence_parser: Optional[SentenceParser] = None
    ):
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
        
        accumulated_text = ""
        sentence_order = 0
        
        try:
            async for chunk in llm_stream:
                if self._interrupted:
                    logger.info("TTS playback interrupted")
                    break
                
                accumulated_text += chunk
                
                # Check if we have complete sentences
                sentences = sentence_parser.split_into_sentences(accumulated_text)
                
                if len(sentences) > 1:
                    # Process all complete sentences (all but the last one)
                    complete_sentences = sentences[:-1]
                    
                    # Merge short sentences
                    merged = sentence_parser.merge_short_sentences(complete_sentences)
                    
                    # Create TTS tasks for complete sentences
                    for sentence in merged:
                        await self._synthesize_and_queue(sentence, sentence_order)
                        sentence_order += 1
                    
                    # Keep the incomplete last sentence
                    accumulated_text = sentences[-1]
            
            # Process any remaining text
            if accumulated_text.strip() and not self._interrupted:
                await self._synthesize_and_queue(accumulated_text.strip(), sentence_order)
            
            # Wait for all chunks to be played
            if not self._interrupted:
                await self._wait_for_completion()
                
        except Exception as e:
            logger.error(f"Error in TTS playback: {e}", exc_info=True)
            raise
        finally:
            self._processing = False
    
    async def _synthesize_and_queue(self, text: str, order: int) -> None:
        """
        Synthesize text to audio and queue for playback.
        
        Args:
            text: Text to synthesize
            order: Playback order
        """
        logger.info(f"Synthesizing sentence {order}: {text[:50]}...")
        
        # Create chunk entry
        chunk = SentenceChunk(order=order, text=text)
        async with self._lock:
            self._chunks[order] = chunk
        
        # Start synthesis task
        asyncio.create_task(self._synthesize_chunk(order, text))
    
    async def _synthesize_chunk(self, order: int, text: str) -> None:
        """
        Synthesize audio for a chunk and mark it ready.
        
        Args:
            order: Chunk order
            text: Text to synthesize
        """
        try:
            # Collect all audio chunks from the stream
            audio_chunks = []
            async for audio_chunk in self.tts_service.synthesize_stream(text):
                if audio_chunk:
                    audio_chunks.append(audio_chunk)
            
            audio_data = b''.join(audio_chunks)
            
            async with self._lock:
                if order in self._chunks:
                    self._chunks[order].audio_data = audio_data
                    self._chunks[order].is_ready = True
                    logger.info(f"Audio ready for chunk {order} ({len(audio_data)} bytes)")
            
            # Try to play chunks in order
            await self._play_ready_chunks()
            
        except Exception as e:
            logger.error(f"Error synthesizing chunk {order}: {e}", exc_info=True)
    
    async def _play_ready_chunks(self) -> None:
        """Play chunks in order if they're ready."""
        async with self._lock:
            while self._next_to_play in self._chunks:
                chunk = self._chunks[self._next_to_play]
                
                if not chunk.is_ready:
                    break
                
                if chunk.audio_data:
                    logger.info(f"Playing chunk {chunk.order}")
                    await self.on_audio_ready(chunk.audio_data)
                
                # Remove played chunk and move to next
                del self._chunks[self._next_to_play]
                self._next_to_play += 1
    
    async def _wait_for_completion(self) -> None:
        """Wait for all chunks to be played."""
        max_wait = 30  # Maximum wait time in seconds
        wait_interval = 0.1
        waited = 0
        
        while waited < max_wait:
            async with self._lock:
                if not self._chunks:
                    return
            
            await asyncio.sleep(wait_interval)
            waited += wait_interval
        
        logger.warning(f"Timeout waiting for TTS completion, {len(self._chunks)} chunks pending")
    
    def interrupt(self):
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
        """Clear all pending chunks and reset playback position."""
        async with self._lock:
            self._chunks.clear()
            self._next_to_play = 0
