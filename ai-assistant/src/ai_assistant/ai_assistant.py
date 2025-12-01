"""
AI Assistant
Core logic for speech-to-text, LLM processing, and text-to-speech.
"""
import asyncio
import logging
import os
from typing import AsyncIterator, Optional, Callable
from google.cloud import speech_v1 as speech
from google.cloud.speech_v1 import SpeechAsyncClient
from google.cloud import texttospeech_v1 as tts
from google.cloud.texttospeech_v1 import TextToSpeechAsyncClient

# LangChain imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, SystemMessagePromptTemplate
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

from .prompts_templates import GREETING_AND_TRIAGE_PROMPT, TRIAGE_CONVERSATION_PROMPT, FINALIZE_SERVICE_REQUEST_PROMPT
from .data_provider import get_data_provider
from .test_data import detect_category  # Keep category detection for now
import json
from .weaviate_models import ChatMessageModelWeaviate
from .definitions import (
    AGENT_NAME,
    COMPANY_NAME,
    USER_NAME_PLACEHOLDER,
    MAX_PROVIDERS_TO_PRESENT,
    ConversationStage,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_TOP_K,
    LLM_TOP_P,
    LLM_MAX_OUTPUT_TOKENS,
    STT_SAMPLE_RATE_HZ,
    STT_AUDIO_CHANNEL_COUNT,
    STT_ENABLE_AUTOMATIC_PUNCTUATION,
    STT_MODEL,
    STT_USE_ENHANCED,
    STT_INTERIM_RESULTS,
    STT_SINGLE_UTTERANCE,
    TTS_SAMPLE_RATE_HZ,
    TTS_CHUNK_SIZE,
)

logger = logging.getLogger(__name__)
import random

class PersistentChatMessageHistory(BaseChatMessageHistory):
    """Chat history that automatically persists messages to Weaviate."""

    def __init__(self, user_id: str, session_id: str, stage_getter: Callable[[], str]):
        self._user_id = user_id
        self._session_id = session_id
        self._stage_getter = stage_getter
        self._is_loading = False
        self._loaded = False
        self._messages: list[BaseMessage] = []

    @property
    def messages(self) -> list[BaseMessage]:
        """Return the list of messages."""
        return self._messages

    def load_from_store(self):
        """Load previously persisted messages into memory once."""
        if self._loaded or not self._user_id:
            return
        messages = ChatMessageModelWeaviate.get_messages(self._user_id)
        if not messages:
            self._loaded = True
            return
        self._is_loading = True
        try:
            for msg in messages:
                content = msg.get("content")
                role = msg.get("role", "assistant")
                if not content:
                    continue
                if role == "human":
                    self._messages.append(HumanMessage(content=content))
                else:
                    self._messages.append(AIMessage(content=content))
        finally:
            self._is_loading = False
            self._loaded = True

    def add_message(self, message: BaseMessage) -> None:
        """Add a message to the history and persist it."""
        self._messages.append(message)
        if self._is_loading or not self._user_id:
            return

        role = "human" if isinstance(message, HumanMessage) else "assistant"
        content = getattr(message, "content", "")
        if not content:
            return

        ChatMessageModelWeaviate.save_message(
            user_id=self._user_id,
            session_id=self._session_id,
            role=role,
            content=content,
            stage=self._stage_getter(),
        )
    
    def clear(self) -> None:
        """Clear all messages from history."""
        self._messages = []


class AIAssistant:
    """AI Assistant using Google Cloud services with gRPC streaming and LangChain."""
    
    def __init__(self, gemini_api_key: str, language_code: str = 'de-DE', 
                 voice_name: str = 'de-DE-Chirp3-HD-Sulafat',
                 user_id: Optional[str] = None):
        self.language_code = language_code
        self.voice_name = voice_name
        self.user_id = user_id or "anonymous"
        self.gemini_api_key = gemini_api_key
        
        # Initialize data provider (Weaviate or local test data)
        self.data_provider = get_data_provider()
        
        # Conversation state
        self.current_stage = ConversationStage.GREETING
        self.conversation_context = {
            "user_problem": "",
            "detected_category": None,
            "providers_found": [],
            "current_provider_index": 0,
        }
        
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
            model=LLM_MODEL,
            google_api_key=gemini_api_key,
            temperature=LLM_TEMPERATURE,
            top_k=LLM_TOP_K,
            top_p=LLM_TOP_P,
            max_output_tokens=LLM_MAX_OUTPUT_TOKENS,
            streaming=True,
        )
        
        # Initialize chat message history (in-memory store keyed by session_id)
        self.store = {}
        
        # We'll create prompts dynamically based on stage
        # Initial prompt is TRIAGE (after greeting)
        self.current_prompt = self._create_prompt_for_stage(ConversationStage.TRIAGE)
        self.chain = self.current_prompt | self.llm
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
            history = PersistentChatMessageHistory(
                user_id=self.user_id,
                session_id=session_id,
                stage_getter=lambda: self.current_stage,
            )
            history.load_from_store()
            self.store[session_id] = history
        return self.store[session_id]

    def clear_conversation_history(self, clear_persistent: bool = False):
        """Clear chat history from memory and optionally from Weaviate."""
        if self.user_id in self.store:
            del self.store[self.user_id]
        if clear_persistent and self.user_id:
            ChatMessageModelWeaviate.delete_messages(self.user_id)
    
    def _create_prompt_for_stage(self, stage: str) -> ChatPromptTemplate:
        """Create appropriate prompt template based on conversation stage."""
        if stage == ConversationStage.GREETING:
            return ChatPromptTemplate.from_messages([
                SystemMessagePromptTemplate.from_template(GREETING_AND_TRIAGE_PROMPT),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}")
            ])
        elif stage == ConversationStage.TRIAGE:
            return ChatPromptTemplate.from_messages([
                SystemMessagePromptTemplate.from_template(TRIAGE_CONVERSATION_PROMPT).format(
                    agent_name=AGENT_NAME,
                ),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}")
            ])
        elif stage == ConversationStage.FINALIZE:
            provider_list_json = json.dumps(self.conversation_context["providers_found"], ensure_ascii=False)
            provider_count = len(self.conversation_context["providers_found"])
            return ChatPromptTemplate.from_messages([
                SystemMessagePromptTemplate.from_template(FINALIZE_SERVICE_REQUEST_PROMPT).format(
                    agent_name=AGENT_NAME,
                    provider_list_json=provider_list_json,
                    provider_count=provider_count,
                ),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}")
            ])
        else:
            # Default to triage
            return self._create_prompt_for_stage(ConversationStage.TRIAGE)
    
    def _update_chain_for_stage(self, stage: str):
        """Update the chain with new prompt for the given stage."""
        self.current_stage = stage
        self.current_prompt = self._create_prompt_for_stage(stage)
        self.chain = self.current_prompt | self.llm
        self.chain_with_history = RunnableWithMessageHistory(
            self.chain,
            self._get_session_history,
            input_messages_key="input",
            history_messages_key="history",
        )
        logger.info(f"Updated conversation stage to: {stage}")
    
    async def _detect_stage_transition(self, user_input: str, ai_response: str) -> Optional[str]:
        """
        Detect if conversation should transition to a new stage based on context.
        
        Returns:
            New stage name if transition detected, None otherwise
        """
        user_lower = user_input.lower()
        response_lower = ai_response.lower()
        
        # Detect transition from TRIAGE to FINALIZE
        # Look for confirmation keywords and the transition message
        if self.current_stage == ConversationStage.TRIAGE:
            transition_keywords = [
                "database durchsuchen",
                "datenbank durchsuchen", 
                "einen moment",
                "please hold",
                "bitte warten"
            ]
            if any(keyword in response_lower for keyword in transition_keywords):
                logger.info("Detected transition trigger to FINALIZE stage")
                # Accumulate conversation context for provider search
                await self._accumulate_problem_description(user_input)
                return ConversationStage.FINALIZE
        
        # Detect transition from FINALIZE to COMPLETED
        if self.current_stage == ConversationStage.FINALIZE:
            closing_keywords = [
                "schönen tag",
                "auf wiedersehen",
                "vielen dank",
                "thank you"
            ]
            if any(keyword in response_lower for keyword in closing_keywords):
                return ConversationStage.COMPLETED
        
        return None
    
    async def _accumulate_problem_description(self, user_input: str):
        """Accumulate user's problem description for provider search using data provider."""
        self.conversation_context["user_problem"] += " " + user_input
        
        # Detect category from accumulated text
        category = detect_category(self.conversation_context["user_problem"])
        if category:
            self.conversation_context["detected_category"] = category
            logger.info(f"Detected category: {category}")
        
        # Search for providers using data provider (Weaviate or local)
        providers = await self.data_provider.search_providers(
            query_text=self.conversation_context["user_problem"],
            category=self.conversation_context["detected_category"],
            limit=MAX_PROVIDERS_TO_PRESENT
        )
        
        self.conversation_context["providers_found"] = providers
        logger.info(f"Found {len(providers)} matching providers via data provider")
    
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
                sample_rate_hertz=STT_SAMPLE_RATE_HZ,
                language_code=self.language_code,
                audio_channel_count=STT_AUDIO_CHANNEL_COUNT,
                enable_automatic_punctuation=STT_ENABLE_AUTOMATIC_PUNCTUATION,
                model=STT_MODEL,
                use_enhanced=STT_USE_ENHANCED
            )
            
            streaming_config = speech.StreamingRecognitionConfig(
                config=config,
                interim_results=STT_INTERIM_RESULTS,  # Enable interim results to show progress
                single_utterance=STT_SINGLE_UTTERANCE,  # Keep listening continuously
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
                            logger.debug(f"Sent {chunk_count} audio chunks to STT")
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
            logger.debug(f"Generating LLM response for: '{prompt[:50]}...' [Stage: {self.current_stage}]")
            
            # Accumulate problem description during triage
            if self.current_stage == ConversationStage.TRIAGE:
                await self._accumulate_problem_description(prompt)
            
            # Stream response chunks using LangChain
            # Note: RunnableWithMessageHistory automatically adds both user and AI messages to history
            full_response = ""
            async for chunk in self.chain_with_history.astream(
                {"input": prompt},
                config={"configurable": {"session_id": self.user_id}}
            ):
                if chunk.content:
                    logger.debug(f"LLM stream chunk: '{chunk.content}'")
                    full_response += chunk.content
                    yield chunk.content
            
            # Check for stage transitions after complete response
            new_stage = await self._detect_stage_transition(prompt, full_response)
            if new_stage == ConversationStage.FINALIZE:
                logger.info(f"Stage transition detected: {self.current_stage} -> {new_stage}")
                self._update_chain_for_stage(new_stage)
                
                # Automatically generate provider presentation without user input
                logger.info("Auto-generating provider presentation in FINALIZE stage")
                
                # Use an empty/neutral prompt that signals to start presentation
                # The FINALIZE prompt instructs the agent to automatically present
                auto_prompt = " "  # Minimal prompt to trigger the chain
                
                # Stream the provider presentation directly
                # RunnableWithMessageHistory will automatically save both the prompt and response
                async for chunk in self.chain_with_history.astream(
                    {"input": auto_prompt},
                    config={"configurable": {"session_id": self.user_id}}
                ):
                    if chunk.content:
                        logger.debug(f"LLM auto-presentation chunk: '{chunk.content}'")
                        yield chunk.content
                        
            elif new_stage:
                logger.info(f"Stage transition detected: {self.current_stage} -> {new_stage}")
                self._update_chain_for_stage(new_stage)
            
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
                sample_rate_hertz=TTS_SAMPLE_RATE_HZ,  # Match WebRTC's native rate - no resampling needed!
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
            chunk_size = TTS_CHUNK_SIZE
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
            # Set stage to greeting
            self._update_chain_for_stage(ConversationStage.GREETING)
            
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
            
            # After greeting, transition to triage stage
            self._update_chain_for_stage(ConversationStage.TRIAGE)
            
            return full_greeting.strip()
            
        except Exception as e:
            logger.error(f"Error generating greeting: {e}", exc_info=True)
            # Fallback to a simple greeting
            self._update_chain_for_stage(ConversationStage.TRIAGE)
            return "Hallo! Wie kann ich dir heute helfen?"
    
    async def get_greeting_audio(self, user_id: Optional[str] = None) -> tuple[str, AsyncIterator[bytes]]:
        """Generate a natural greeting and return both text and TTS audio.
        
        Args:
            user_id: Optional user ID to fetch user data from data provider
        
        Returns:
            tuple: (greeting_text, audio_iterator)
        """
        # Try to fetch user data from data provider if user_id provided
        user_name = USER_NAME_PLACEHOLDER
        has_open_request = False
        
        if user_id:
            user = await self.data_provider.get_user_by_id(user_id)
            if user:
                # Get the full name and extract first name
                full_name = user.get("name", USER_NAME_PLACEHOLDER)
                if full_name and full_name != USER_NAME_PLACEHOLDER:
                    # Split by space and take first name
                    user_name = full_name.split()[0] if full_name.split() else full_name
                    logger.info(f"Using first name for greeting: '{user_name}' (from full name: '{full_name}')")
                else:
                    user_name = USER_NAME_PLACEHOLDER
                    logger.debug(f"No valid name found for user {user_id}, using placeholder")
                
                has_open_request = user.get("has_open_request", False)
            else:
                logger.warning(f"User {user_id} not found in database, using placeholder name")
        else:
            logger.debug("No user_id provided for greeting, using placeholder name")
        
        # Generate greeting text using LLM
        greeting_text = await self.generate_greeting(
            user_name=user_name, 
            has_open_request=has_open_request
        )
        
        # Add greeting to chat history
        history = self._get_session_history(self.user_id)
        history.add_message(AIMessage(content=greeting_text))
        
        # Generate audio stream
        logger.info(f"Generating greeting audio: '{greeting_text}'")
        
        # Return both the text and the audio generator
        return greeting_text, self.text_to_speech_stream(greeting_text)
