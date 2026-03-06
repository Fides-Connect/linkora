"""
LLM Service
Handles all language model interactions.
"""
import json
import logging
from typing import AsyncIterator, Optional, Dict, Any, List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, SystemMessagePromptTemplate
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# signal_transition — Gemini function-calling schema
# ─────────────────────────────────────────────────────────────────────────────

SIGNAL_TRANSITION_SCHEMA: Dict[str, Any] = {
    "name": "signal_transition",
    "description": (
        "Advance the conversation to the specified stage when you have gathered "
        "sufficient information to do so. Only call this when you are confident "
        "the transition is appropriate given the current conversation."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "target_stage": {
                "type": "string",
                "description": (
                    "The stage to transition to. "
                    "Allowed values: triage, clarify, tool_execution, "
                    "confirmation, finalize, recovery, completed."
                ),
            },
        },
        "required": ["target_stage"],
    },
}



class LLMService:
    """Service for language model interactions using LangChain and Gemini."""
    
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash",
                 temperature: float = 0.2, max_output_tokens: int = 512):
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
            top_k=4,
            top_p=0.9,
            max_output_tokens=max_output_tokens,
            streaming=True,
        )
        
        self.session_store: Dict[str, BaseChatMessageHistory] = {}
        # Per-session Gemini function schemas (empty = no function calling).
        self._session_functions: Dict[str, List[Dict[str, Any]]] = {}
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

    def register_functions(self, session_id: str, tool_schemas: List[Dict[str, Any]]) -> None:
        """
        Register (or replace) Gemini function-calling schemas for a session.

        When at least one schema is registered, the LLM will be bound with those
        tools for calls in that session so it can emit function-call chunks.
        Pass an empty list to disable function calling for the session.

        Args:
            session_id:   Session identifier.
            tool_schemas: List of Gemini function-call schemas to register.
        """
        self._session_functions[session_id] = list(tool_schemas)
        logger.debug(
            "Registered %d function(s) for session %s", len(tool_schemas), session_id
        )

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
    
    def create_chain_with_history(
        self,
        prompt_template: ChatPromptTemplate,
        session_id: str,
        tool_schemas: Optional[List[Dict[str, Any]]] = None,
    ):
        """
        Create a runnable chain with message history.
        
        Args:
            prompt_template: Prompt template to use
            session_id: Session identifier
            tool_schemas: Optional list of function-calling schemas to bind.
        
        Returns:
            RunnableWithMessageHistory instance
        """
        llm = self.llm.bind_tools(tool_schemas) if tool_schemas else self.llm
        chain = prompt_template | llm
        
        chain_with_history = RunnableWithMessageHistory(
            chain,
            lambda sid: self.get_session_history(sid),
            input_messages_key="input",
            history_messages_key="history",
        )
        
        logger.debug(f"Created chain with history for session: {session_id}")
        return chain_with_history
    
    async def generate_stream(
        self,
        prompt: str,
        prompt_template: ChatPromptTemplate,
        session_id: str,
    ) -> AsyncIterator:
        """
        Generate streaming response from LLM.

        Yields plain strings for text chunks and dicts of the form
        ``{"type": "function_call", "name": "...", "args": {...}}``
        for any function calls the model makes.

        Args:
            prompt: User input prompt
            prompt_template: Prompt template to use
            session_id: Session identifier
        """
        try:
            session_tools = self._session_functions.get(session_id, [])
            chain_with_history = self.create_chain_with_history(
                prompt_template, session_id, session_tools or None
            )
            
            logger.debug(f"Generating LLM response for: '{prompt[:50]}...'")

            # Buffer for assembling multi-chunk tool calls (keyed by index)
            tcc_buffer: Dict[int, Dict[str, str]] = {}

            async for chunk in chain_with_history.astream(
                {"input": prompt},
                config={"configurable": {"session_id": session_id}}
            ):
                tool_call_chunks = getattr(chunk, "tool_call_chunks", None) or []

                if tool_call_chunks:
                    # Accumulate tool call argument fragments
                    for tc in tool_call_chunks:
                        if isinstance(tc, dict):
                            idx = tc.get("index", 0) or 0
                            name = tc.get("name") or ""
                            args = tc.get("args") or ""
                        else:
                            idx = getattr(tc, "index", 0) or 0
                            name = getattr(tc, "name", "") or ""
                            args = getattr(tc, "args", "") or ""

                        if idx not in tcc_buffer:
                            tcc_buffer[idx] = {"name": "", "args_str": ""}
                        if name:
                            tcc_buffer[idx]["name"] = name
                        tcc_buffer[idx]["args_str"] += args
                else:
                    # Non-tool-call chunk: flush completed tool calls first
                    for item in tcc_buffer.values():
                        if item["name"]:
                            try:
                                fn_args = json.loads(item["args_str"]) if item["args_str"] else {}
                            except json.JSONDecodeError:
                                fn_args = {"raw": item["args_str"]}
                            yield {
                                "type": "function_call",
                                "name": item["name"],
                                "args": fn_args,
                            }
                    tcc_buffer = {}

                    # Yield text content
                    if chunk.content:
                        text = self._content_to_text(chunk.content)
                        logger.debug(f"LLM stream chunk: '{text}'")
                        if text:
                            yield text

            # Flush any remaining buffered tool calls
            for item in tcc_buffer.values():
                if item["name"]:
                    try:
                        fn_args = json.loads(item["args_str"]) if item["args_str"] else {}
                    except json.JSONDecodeError:
                        fn_args = {"raw": item["args_str"]}
                    yield {
                        "type": "function_call",
                        "name": item["name"],
                        "args": fn_args,
                    }
            
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
