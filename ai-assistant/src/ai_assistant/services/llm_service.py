"""
LLM Service
Handles all language model interactions.
"""
import logging
from typing import AsyncIterator, Optional, Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, SystemMessagePromptTemplate
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

logger = logging.getLogger(__name__)


class LLMService:
    """Service for language model interactions using LangChain and Gemini."""
    
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash",
                 temperature: float = 0.2, max_output_tokens: int = 2048):
        """
        Initialize LLM service.
        
        Args:
            api_key: Gemini API key
            model: Model name to use
            temperature: Sampling temperature
            max_output_tokens: Maximum output tokens
        """
        self.llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=temperature,
            top_k=8,
            top_p=0.9,
            max_output_tokens=max_output_tokens,
            streaming=True,
        )
        
        self.session_store: Dict[str, BaseChatMessageHistory] = {}
        logger.info(f"LLM service initialized with model: {model}")
    
    def get_session_history(self, session_id: str) -> BaseChatMessageHistory:
        """
        Get or create chat message history for a session.
        
        Args:
            session_id: Session identifier
        
        Returns:
            Chat message history for the session
        """
        if session_id not in self.session_store:
            self.session_store[session_id] = ChatMessageHistory()
            logger.debug(f"Created new chat history for session: {session_id}")
        return self.session_store[session_id]
    
    def add_message_to_history(self, session_id: str, message):
        """
        Add a message to session history.
        
        Args:
            session_id: Session identifier
            message: Message to add (AIMessage or HumanMessage)
        """
        history = self.get_session_history(session_id)
        history.add_message(message)
        logger.debug(f"Added message to session {session_id}: {type(message).__name__}")

    @staticmethod
    def _content_to_text(content: Any) -> str:
        """Normalize chunk content to plain text for models that return structured parts."""
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    # Gemini can return part dicts like {"text": "..."}
                    text = item.get("text")
                    if text:
                        parts.append(text)
                else:
                    text = getattr(item, "text", None)
                    if text:
                        parts.append(text)
            return "".join(parts)

        return str(content)
    
    def create_chain_with_history(self, prompt_template: ChatPromptTemplate, session_id: str):
        """
        Create a runnable chain with message history.
        
        Args:
            prompt_template: Prompt template to use
            session_id: Session identifier
        
        Returns:
            RunnableWithMessageHistory instance
        """
        chain = prompt_template | self.llm
        
        chain_with_history = RunnableWithMessageHistory(
            chain,
            lambda sid: self.get_session_history(sid),
            input_messages_key="input",
            history_messages_key="history",
        )
        
        logger.debug(f"Created chain with history for session: {session_id}")
        return chain_with_history
    
    async def generate_stream(self, prompt: str, prompt_template: ChatPromptTemplate,
                             session_id: str) -> AsyncIterator[str]:
        """
        Generate streaming response from LLM.
        
        Args:
            prompt: User input prompt
            prompt_template: Prompt template to use
            session_id: Session identifier
        
        Yields:
            Response chunks as strings
        """
        try:
            chain_with_history = self.create_chain_with_history(prompt_template, session_id)
            
            logger.debug(f"Generating LLM response for: '{prompt[:50]}...'")
            
            async for chunk in chain_with_history.astream(
                {"input": prompt},
                config={"configurable": {"session_id": session_id}}
            ):
                if chunk.content:
                    text = self._content_to_text(chunk.content)
                    logger.debug(f"LLM stream chunk: '{text}'")
                    if text:
                        yield text
            
        except Exception as e:
            logger.error(f"LLM generation error: {e}", exc_info=True)
            yield "Entschuldigung, ich konnte keine Antwort generieren."
    
    async def generate(self, messages: list) -> str:
        """
        Generate a single response from LLM without streaming.
        
        Args:
            messages: List of messages to send to LLM
        
        Returns:
            Complete response as string
        """
        try:
            full_response = ""
            async for chunk in self.llm.astream(messages):
                if chunk.content:
                    full_response += self._content_to_text(chunk.content)
            
            logger.debug(f"Generated response: '{full_response[:100]}...'")
            return full_response.strip()
            
        except Exception as e:
            logger.error(f"LLM generation error: {e}", exc_info=True)
            return "Entschuldigung, ich konnte keine Antwort generieren."
