"""
AI Assistant
Core logic for speech-to-text, LLM processing, and text-to-speech.
"""
import asyncio
import logging
import os
from typing import AsyncIterator, Optional
from google.cloud import speech_v1 as speech
from google.cloud.speech_v1 import SpeechAsyncClient
from google.cloud import texttospeech_v1 as tts
from google.cloud.texttospeech_v1 import TextToSpeechAsyncClient

# LangChain imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, SystemMessagePromptTemplate
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

from .prompts_templates import GREETING_AND_TRIAGE_PROMPT, TRIAGE_CONVERSATION_PROMPT

logger = logging.getLogger(__name__)
import random

# Constants
AGENT_NAME = "Elin"
COMPANY_NAME = "FidesConnect"
USER_NAME_PLACEHOLDER = "Wolfgang"
HAS_OPEN_REQUEST_PLACEHOLDER = random.choice([True, False])

class AIAssistant:
    """AI Assistant using Google Cloud services with gRPC streaming and LangChain."""
    
    def __init__(self, gemini_api_key: str, language_code: str = 'de-DE', 
                 voice_name: str = 'de-DE-Chirp3-HD-Sulafat',
                 session_id: Optional[str] = None):
        self.language_code = language_code
        self.voice_name = voice_name
        self.session_id = session_id or "default"
        
        # Initialize Google Cloud clients with async gRPC
        # Use default credentials in Cloud Run (via service account)
        # Use explicit credentials locally (via GOOGLE_APPLICATION_CREDENTIALS)
        credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if credentials_path and os.path.exists(credentials_path):
            logger.info(f"Using credentials from: {credentials_path}")
            # For async clients, we'll use the sync client's credentials
            from google.oauth2 import service_account
            credentials = service_account.Credentials.from_service_account_file(credentials_path)
            self.speech_client = SpeechAsyncClient(credentials=credentials)
            self.tts_client = TextToSpeechAsyncClient(credentials=credentials)
        else:
            logger.info("Using default credentials (Cloud Run environment)")
            self.speech_client = SpeechAsyncClient()
            self.tts_client = TextToSpeechAsyncClient()
        
        # Initialize LangChain LLM with streaming support
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            google_api_key=gemini_api_key,
            temperature=0.9,
            top_k=8,
            top_p=0.9,
            max_output_tokens=512,
            streaming=True,
        )
        
        # Initialize chat message history
        self.store = {}  # Session store for chat histories
        
        prompt_template = ChatPromptTemplate.from_messages(
                [SystemMessagePromptTemplate.from_template(TRIAGE_CONVERSATION_PROMPT).format(
                        agent_name=AGENT_NAME,
                    ),
                 MessagesPlaceholder(variable_name="history"),
                 ("human", "{input}")]
            )
        self.prompt = prompt_template
        
        
        # Create chain with message history
        self.chain = self.prompt | self.llm
        self.chain_with_history = RunnableWithMessageHistory(
            self.chain,
            self._get_session_history,
            input_messages_key="input",
            history_messages_key="history",
        )
        
        logger.info("AI Assistant initialized with LangChain and gRPC streaming")
        # Semaphore to limit concurrent Google API TTS requests for rate limiting
        # Default to 5 but allow override via environment variable for testing
        max_concurrency = int(os.getenv('GOOGLE_TTS_API_CONCURRENCY', '5'))
        self.google_tts_api_semaphore = asyncio.Semaphore(max_concurrency)
    
    def _get_session_history(self, session_id: str) -> BaseChatMessageHistory:
        """Get or create chat message history for a session."""
        if session_id not in self.store:
            self.store[session_id] = ChatMessageHistory()
            # Greeting will be generated and added dynamically when needed
        return self.store[session_id]
    
    async def speech_to_text_continuous_stream(self, audio_generator) -> AsyncIterator[tuple[str, bool]]:
        """
        Continuously stream audio to STT using async gRPC and yield (transcript, is_final) tuples.
        This method accepts an async generator that yields audio chunks.
        Returns tuples of (transcript, is_final) where is_final indicates if the result is final.
        
        Uses native async gRPC streaming for optimal latency.
        """
        try:
            # Configure streaming recognition
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=48000,
                language_code=self.language_code,
                audio_channel_count=1,
                enable_automatic_punctuation=True,
                model='latest_long',
                use_enhanced=True
            )
            
            streaming_config = speech.StreamingRecognitionConfig(
                config=config,
                interim_results=True,  # Enable interim results to show progress
                single_utterance=False,  # Keep listening continuously
            )
            
            # Create async generator for gRPC requests
            async def request_generator():
                """Generate streaming recognition requests."""
                # First request with config
                yield speech.StreamingRecognizeRequest(streaming_config=streaming_config)
                
                # Then stream audio chunks
                chunk_count = 0
                async for audio_chunk in audio_generator:
                    if audio_chunk:
                        chunk_count += 1
                        if chunk_count == 1:
                            logger.info(f"Sent first audio chunk to STT ({len(audio_chunk)} bytes)")
                        elif chunk_count % 50 == 0:
                            logger.info(f"Sent {chunk_count} audio chunks to STT")
                        yield speech.StreamingRecognizeRequest(audio_content=audio_chunk)
                
                logger.info(f"Audio generator finished after {chunk_count} chunks")
            
            # Perform async gRPC streaming recognition
            logger.info("Starting async gRPC streaming recognition")
            stream = await self.speech_client.streaming_recognize(requests=request_generator())

            # Process responses asynchronously
            async for response in stream:
                for result in response.results:
                    if result.alternatives:
                        transcript = result.alternatives[0].transcript
                        is_final = result.is_final
                        logger.debug(f"STT continuous: '{transcript}' (final={is_final})")
                        yield (transcript, is_final)
            
            logger.info("Async gRPC streaming recognition completed")
            
        except Exception as e:
            logger.error(f"Continuous streaming speech-to-text error: {e}", exc_info=True)
            yield ("", False)
    
    async def generate_llm_response_stream(self, prompt: str) -> AsyncIterator[str]:
        """Generate streaming response using LangChain with Gemini LLM for low latency."""
        try:
            # Use LangChain's streaming with message history
            logger.debug(f"Generating LLM response for: '{prompt[:50]}...'")
            
            # Stream response chunks using LangChain
            async for chunk in self.chain_with_history.astream(
                {"input": prompt},
                config={"configurable": {"session_id": self.session_id}}
            ):
                if chunk.content:
                    logger.debug(f"LLM stream chunk: '{chunk.content}'")
                    yield chunk.content
            
        except Exception as e:
            logger.error(f"Streaming LLM generation error: {e}", exc_info=True)
            yield "Entschuldigung, ich konnte keine Antwort generieren."
    
    async def text_to_speech_stream(self, text: str) -> AsyncIterator[bytes]:
        """Convert text to speech using Google Cloud TTS async gRPC API."""
        try:
            # Configure TTS request
            synthesis_input = tts.SynthesisInput(text=text)
            
            voice = tts.VoiceSelectionParams(
                language_code=self.language_code,
                name=self.voice_name,
            )
            
            audio_config = tts.AudioConfig(
                audio_encoding=tts.AudioEncoding.LINEAR16,
                sample_rate_hertz=48000,  # Match WebRTC's native rate - no resampling needed!
            )
            
            # Perform async synthesis using gRPC under semaphore control
            logger.debug(f"Starting async TTS synthesis for text: '{text[:50]}...' (acquiring semaphore)")
            async with self.google_tts_api_semaphore:
                logger.debug("Semaphore acquired for TTS synthesis")
                response = await self.tts_client.synthesize_speech(
                    input=synthesis_input,
                    voice=voice,
                    audio_config=audio_config
                )
            
            # Stream audio in chunks (larger chunks = fewer iterations = lower overhead)
            chunk_size = 2048
            audio_content = response.audio_content
            
            logger.debug(f"TTS synthesis complete, streaming {len(audio_content)} bytes in chunks of {chunk_size}")
            
            for i in range(0, len(audio_content), chunk_size):
                chunk = audio_content[i:i + chunk_size]
                yield chunk
                # No artificial delay - stream as fast as possible for lowest latency
                
        except Exception as e:
            logger.error(f"Text-to-speech error: {e}", exc_info=True)
            # Return empty bytes on error
            yield b''
    
    async def generate_greeting(self, user_name: str = "", has_open_request: bool = False) -> str:
        """Generate a natural, friendly greeting using the LLM."""
        try:
            prompt_template = ChatPromptTemplate.from_messages(
                [SystemMessagePromptTemplate.from_template(GREETING_AND_TRIAGE_PROMPT),
                 HumanMessage(content=" ")] # Gemini-API requires [SystemMessage, HumanMessage] to generate the first AIMessage.
            )
            greeting_message = prompt_template.format_messages(
                agent_name=AGENT_NAME,
                company_name=COMPANY_NAME,
                user_name=user_name,
                has_open_request="YES" if has_open_request else "NO",
            )
            
            full_greeting = ""
            async for chunk in self.llm.astream(greeting_message):
                if chunk.content:
                    full_greeting += chunk.content
            
            logger.info(f"Generated greeting: '{full_greeting}'")
            return full_greeting.strip()
            
        except Exception as e:
            logger.error(f"Error generating greeting: {e}", exc_info=True)
            # Fallback to a simple greeting
            return "Hallo! Wie kann ich dir heute helfen?"
    
    async def get_greeting_audio(self) -> tuple[str, AsyncIterator[bytes]]:
        """Generate a natural greeting and return both text and TTS audio.
        
        Returns:
            tuple: (greeting_text, audio_iterator)
        """
        # Generate greeting text using LLM
        greeting_text = await self.generate_greeting(
            user_name=USER_NAME_PLACEHOLDER, 
            has_open_request=HAS_OPEN_REQUEST_PLACEHOLDER
        )
        
        # Add greeting to chat history
        history = self._get_session_history(self.session_id)
        history.add_message(AIMessage(content=greeting_text))
        
        # Generate audio stream
        logger.info(f"Generating greeting audio: '{greeting_text}'")
        
        # Return both the text and the audio generator
        return greeting_text, self.text_to_speech_stream(greeting_text)
