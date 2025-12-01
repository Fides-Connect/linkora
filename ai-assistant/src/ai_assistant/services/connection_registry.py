"""
Connection Registry
Manages active peer connections and connection tracking.
"""
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class ConnectionRegistry:
    """Central registry for active peer connections."""

    def __init__(self):
        """Initialize connection registry."""
        self.active_connections: Dict[str, any] = {}

    def register(self, connection_id: str, handler):
        """
        Register a new connection.
        
        Args:
            connection_id: Unique connection identifier
            handler: PeerConnectionHandler instance
        """
        self.active_connections[connection_id] = handler
        logger.info(
            f"Registered connection {connection_id}, "
            f"total connections: {len(self.active_connections)}"
        )

    def unregister(self, connection_id: str) -> bool:
        """
        Unregister a connection.
        
        Args:
            connection_id: Unique connection identifier
            
        Returns:
            True if connection was removed, False if not found
        """
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
            logger.info(
                f"Unregistered connection {connection_id}, "
                f"remaining connections: {len(self.active_connections)}"
            )
            return True
        return False

    def get(self, connection_id: str) -> Optional[any]:
        """
        Get connection handler by ID.
        
        Args:
            connection_id: Unique connection identifier
            
        Returns:
            PeerConnectionHandler instance or None
        """
        return self.active_connections.get(connection_id)

    def get_user_connections(self, user_id: str) -> list:
        """
        Get all connections for a specific user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of connection IDs for the user
        """
        return [
            conn_id
            for conn_id, handler in self.active_connections.items()
            if handler.user_id == user_id
        ]

    def has_user_connections(self, user_id: str) -> bool:
        """
        Check if user has any active connections.
        
        Args:
            user_id: User identifier
            
        Returns:
            True if user has connections
        """
        return any(
            handler.user_id == user_id
            for handler in self.active_connections.values()
        )

    def get_stats(self) -> dict:
        """Get connection statistics."""
        connections_by_user = {}
        for handler in self.active_connections.values():
            user_id = handler.user_id or 'anonymous'
            connections_by_user[user_id] = connections_by_user.get(user_id, 0) + 1

        return {
            'total_connections': len(self.active_connections),
            'unique_users': len(connections_by_user),
            'connections_by_user': connections_by_user,
            'authenticated_users': len([u for u in connections_by_user.keys() if u != 'anonymous']),
            'anonymous_connections': connections_by_user.get('anonymous', 0)
        }

    def count(self) -> int:
        """Get total number of active connections."""
        return len(self.active_connections)

    def clear(self):
        """Clear all connections (for testing)."""
        self.active_connections.clear()
        logger.info("Cleared all connections from registry")
