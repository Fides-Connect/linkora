"""
AI Assistant
Core logic for speech-to-text, LLM processing, and text-to-speech.
"""
import asyncio
import logging
import os
from typing import AsyncIterator
from google.cloud import speech_v1 as speech
from google.cloud import texttospeech_v1 as tts
import google.generativeai as genai

logger = logging.getLogger(__name__)


class AIAssistant:
    """AI Assistant using Google Cloud services."""
    
    def __init__(self, gemini_api_key: str, language_code: str = 'de-DE', 
                 voice_name: str = 'de-DE-Wavenet-F'):
        self.language_code = language_code
        self.voice_name = voice_name
        
        # Initialize Google Cloud Speech client
        self.speech_client = speech.SpeechClient()
        
        # Initialize Google Cloud Text-to-Speech client
        self.tts_client = tts.TextToSpeechClient()
        
        # Initialize Gemini AI
        genai.configure(api_key=gemini_api_key)
        self.llm_model = genai.GenerativeModel('gemini-2.0-flash-exp')
        self.chat_session = self.llm_model.start_chat(history=[])
        
        # Configure generation
        self.generation_config = genai.types.GenerationConfig(
            temperature=0.7,
            top_k=40,
            top_p=0.95,
            max_output_tokens=1024
        )
        
        logger.info("AI Assistant initialized")
    
    async def speech_to_text(self, audio_data: bytes) -> str:
        """Convert speech audio to text using Google Cloud Speech-to-Text."""
        try:
            # Configure recognition
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code=self.language_code,
                audio_channel_count=1,
                enable_automatic_punctuation=True,
            )
            
            audio = speech.RecognitionAudio(content=audio_data)
            
            # Perform synchronous recognition
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.speech_client.recognize(
                    config=config,
                    audio=audio
                )
            )
            
            # Extract transcript
            transcript = ""
            for result in response.results:
                if result.alternatives:
                    transcript += result.alternatives[0].transcript
            
            return transcript.strip()
            
        except Exception as e:
            logger.error(f"Speech-to-text error: {e}", exc_info=True)
            return ""
    
    async def generate_llm_response(self, prompt: str) -> str:
        """Generate response using Gemini LLM."""
        try:
            # Send message to chat session
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.chat_session.send_message(
                    prompt,
                    generation_config=self.generation_config
                )
            )
            
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"LLM generation error: {e}", exc_info=True)
            return "Entschuldigung, ich konnte keine Antwort generieren."
    
    async def text_to_speech_stream(self, text: str) -> AsyncIterator[bytes]:
        """Convert text to speech audio using Google Cloud Text-to-Speech."""
        try:
            # Configure synthesis
            synthesis_input = tts.SynthesisInput(text=text)
            
            voice = tts.VoiceSelectionParams(
                language_code=self.language_code,
                name=self.voice_name
            )
            
            audio_config = tts.AudioConfig(
                audio_encoding=tts.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
            )
            
            # Perform synthesis
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.tts_client.synthesize_speech(
                    input=synthesis_input,
                    voice=voice,
                    audio_config=audio_config
                )
            )
            
            # Stream audio in chunks
            chunk_size = 4096
            audio_content = response.audio_content
            
            for i in range(0, len(audio_content), chunk_size):
                chunk = audio_content[i:i + chunk_size]
                yield chunk
                # Small delay to prevent overwhelming the stream
                await asyncio.sleep(0.01)
                
        except Exception as e:
            logger.error(f"Text-to-speech error: {e}", exc_info=True)
            # Return empty bytes on error
            yield b''
