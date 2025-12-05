"""
User Session Manager
Manages user assistant instances and activity tracking.
"""
import logging
import time
from typing import Dict

logger = logging.getLogger(__name__)


class UserSessionManager:
    """Manages user AI assistant sessions and activity tracking."""

    def __init__(
        self,
        assistant_factory,
        idle_timeout: float = 600.0,
        cleanup_interval: float = 60.0
    ):
        """
        Initialize user session manager.
        
        Args:
            assistant_factory: Callable to create AIAssistant instances
            idle_timeout: Seconds before idle user cleanup
            cleanup_interval: Seconds between cleanup checks
        """
        self.assistant_factory = assistant_factory
        self.idle_timeout = idle_timeout
        self.cleanup_interval = cleanup_interval

        # Track user assistants and activity
        self.user_assistants: Dict[str, any] = {}
        self.user_last_activity: Dict[str, float] = {}

    def get_or_create_assistant(self, user_id: str):
        """
        Get existing assistant or create new one for user.
        
        Args:
            user_id: User identifier
            
        Returns:
            AIAssistant instance for the user
        """
        if user_id not in self.user_assistants:
            logger.info(f"Creating new AIAssistant for user: {user_id}")
            self.user_assistants[user_id] = self.assistant_factory(user_id)
        else:
            logger.debug(f"Reusing existing AIAssistant for user: {user_id}")

        self.update_activity(user_id)
        return self.user_assistants[user_id]

    def update_activity(self, user_id: str):
        """Update last activity timestamp for user."""
        self.user_last_activity[user_id] = time.time()

    def has_active_connections(self, user_id: str, connection_checker) -> bool:
        """
        Check if user has any active connections.
        
        Args:
            user_id: User identifier
            connection_checker: Callable that checks for active connections
            
        Returns:
            True if user has active connections
        """
        return connection_checker(user_id)

    def cleanup_user(self, user_id: str, clear_persistent: bool = False) -> bool:
        """
        Clean up user assistant instance.
        
        Args:
            user_id: User identifier
            clear_persistent: Whether to clear persistent history
            
        Returns:
            True if assistant was removed, False if not found
        """
        if user_id in self.user_assistants:
            logger.info(f"Cleaning up AIAssistant for user: {user_id}")
            assistant = self.user_assistants.pop(user_id)

            try:
                assistant.clear_conversation_history(clear_persistent=clear_persistent)
            except AttributeError:
                logger.debug(f"Assistant for {user_id} has no clear_conversation_history")

            if user_id in self.user_last_activity:
                del self.user_last_activity[user_id]

            return True

        return False

    def cleanup_idle_users(self, connection_checker):
        """
        Clean up idle user assistants with no active connections.
        
        Args:
            connection_checker: Callable to check if user has connections
        """
        current_time = time.time()
        idle_users = []

        for user_id, last_activity in list(self.user_last_activity.items()):
            # Check if user has no active connections and has been idle
            if not self.has_active_connections(user_id, connection_checker):
                idle_duration = current_time - last_activity
                if idle_duration > self.idle_timeout:
                    idle_users.append((user_id, idle_duration))

        for user_id, idle_duration in idle_users:
            logger.info(
                f"Cleaning up idle AIAssistant for user {user_id} "
                f"(idle for {idle_duration:.0f}s)"
            )
            self.cleanup_user(user_id, clear_persistent=False)

        if idle_users:
            logger.info(f"Cleaned up {len(idle_users)} idle user sessions")

    def get_stats(self) -> dict:
        """Get session statistics."""
        return {
            'total_users': len(self.user_assistants),
            'active_users': len(self.user_last_activity)
        }
