"""
Firebase Cloud Messaging (FCM) Notification Service
Handles sending push notifications to users via their FCM tokens.

Supports both Android and iOS platforms with platform-specific optimizations:
- Android: Custom notification channels, priority levels, sound
- iOS: APNS with alert, badge, sound, content-available, and categories
"""
import asyncio
import logging
from typing import Any, List
from firebase_admin import messaging
from ..weaviate_models import UserModelWeaviate

logger = logging.getLogger(__name__)

NOTIFICATION_CHANNEL_ID = "fides_notifications"

class NotificationService:
    """
    Service for sending push notifications via Firebase Cloud Messaging.
    
    Automatically handles platform-specific configuration for Android and iOS.
    """
    
    @staticmethod
    def _build_android_config(priority: str = "high") -> messaging.AndroidConfig:
        """Build Android-specific notification configuration."""
        return messaging.AndroidConfig(
            priority=priority,
            notification=messaging.AndroidNotification(
                sound="default",
                channel_id=NOTIFICATION_CHANNEL_ID,
            ),
        )
    
    @staticmethod
    def _build_apns_config(title: str, body: str, priority: str = "high") -> messaging.APNSConfig:
        """Build iOS/APNS-specific notification configuration."""
        return messaging.APNSConfig(
            headers={
                'apns-priority': '10' if priority == 'high' else '5',
            },
            payload=messaging.APNSPayload(
                aps=messaging.Aps(
                    alert=messaging.ApsAlert(
                        title=title,
                        body=body,
                    ),
                    badge=1,
                    sound="default",
                    content_available=True,
                    category=NOTIFICATION_CHANNEL_ID,
                ),
            ),
        )
    
    @staticmethod
    async def send_to_token(
        fcm_token: str,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
        priority: str = "high"
    ) -> bool:
        """
        Send a notification to a specific FCM token.
        
        Args:
            fcm_token: Firebase Cloud Messaging device token
            title: Notification title
            body: Notification body text
            data: Optional custom data payload (all values must be strings)
            priority: Message priority ('high' or 'normal')
            
        Returns:
            bool: True if notification sent successfully, False otherwise
        """
        try:
            if not fcm_token:
                logger.warning("Cannot send notification: empty FCM token")
                return False
            
            # Build the message
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data or {},
                token=fcm_token,
                android=NotificationService._build_android_config(priority),
                apns=NotificationService._build_apns_config(title, body, priority),
            )
            
            # Send the message using async batch method
            batch_response = await messaging.send_each_async([message])
            response = batch_response.responses[0]
            
            if response.success:
                logger.info(f"Successfully sent notification to token: {fcm_token[:10]}... (message_id: {response.message_id})")
                return True
            else:
                logger.warning(f"Failed to send notification to token: {fcm_token[:10]}...")
                return False
            
        except messaging.UnregisteredError:
            logger.warning(f"FCM token is invalid or unregistered: {fcm_token[:10]}...")
            return False
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            return False
    

    @staticmethod
    async def send_to_user(
        user_id: str,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
        priority: str = "high"
    ) -> bool:
        """
        Send a notification to a user by their user_id.
        Automatically fetches the user's FCM token from the database.
        
        Args:
            user_id: User's unique identifier
            title: Notification title
            body: Notification body text
            data: Optional custom data payload (all values must be strings)
            priority: Message priority ('high' or 'normal')
            
        Returns:
            bool: True if notification sent successfully, False otherwise
        """
        try:
            # Fetch user from database
            user = UserModelWeaviate.get_user_by_id(user_id)
            
            if not user:
                logger.warning(f"Cannot send notification: user not found: {user_id}")
                return False
            
            fcm_token = user.get("fcm_token")
            
            if not fcm_token:
                logger.warning(f"Cannot send notification: user {user_id} has no FCM token")
                return False
            
            # Send notification
            return await NotificationService.send_to_token(
                fcm_token=fcm_token,
                title=title,
                body=body,
                data=data,
                priority=priority
            )
            
        except Exception as e:
            logger.error(f"Error sending notification to user {user_id}: {e}")
            return False
    
    @staticmethod
    async def send_to_multiple_users(
        user_ids: List[str],
        title: str,
        body: str,
        data: dict[str, str] | None = None,
        priority: str = "high",
    ) -> dict[str, bool]:
        """
        Send a notification to multiple users.
        
        Args:
            user_ids: List of user IDs
            title: Notification title
            body: Notification body text
            data: Optional custom data payload (all values must be strings)
            priority: Message priority ('high' or 'normal')
            
        Returns:
            Dict mapping user_id to success status
        """
        # Fetch all FCM tokens in a single query for better performance
        user_token_map = UserModelWeaviate.get_attributes_by_filter(
            filter_attr="user_id",
            filter_values=user_ids,
            return_attr="fcm_token"
        )
        
        # Filter out users without valid FCM tokens
        user_tokens = {
            user_id: token 
            for user_id, token in user_token_map.items() 
            if token
        }
        
        if not user_tokens:
            logger.warning("No valid FCM tokens found for any users")
            return {user_id: False for user_id in user_ids}
        if len(user_tokens) < len(user_ids):
            invalid_users = set(user_ids) - set(user_tokens.keys())
            logger.warning(f"Some users do not have valid FCM tokens: {invalid_users}")
        
        # Send multicast
        multicast_result = await NotificationService.send_multicast(
            fcm_tokens=list(user_tokens.values()),
            title=title,
            body=body,
            data=data,
            priority=priority
        )
        
        # Map results back to user IDs
        results = {}
        token_to_user = {token: user_id for user_id, token in user_tokens.items()}
        
        for idx, token in enumerate(user_tokens.values()):
            user_id = token_to_user[token]
            if idx < len(multicast_result.get("responses", [])):
                response = multicast_result["responses"][idx]
                # Firebase SendResponse always has 'success' attribute
                results[user_id] = response.success
            else:
                # Should not happen, but mark as failed if response is missing
                results[user_id] = False
        
        # Mark users without tokens as failed
        for user_id in user_ids:
            if user_id not in results:
                results[user_id] = False
        
        successful = sum(1 for v in results.values() if v)
        logger.info(f"Multicast sent to {successful}/{len(user_ids)} users")
        return results
        

    @staticmethod
    async def send_multicast(
        fcm_tokens: List[str],
        title: str,
        body: str,
        data: dict[str, str] | None = None,
        priority: str = "high"
    ) -> dict[str, Any]:
        """
        Send the same notification to multiple FCM tokens efficiently.
        Uses FCM multicast for better performance.
        
        Args:
            fcm_tokens: List of FCM device tokens
            title: Notification title
            body: Notification body text
            data: Optional custom data payload (all values must be strings)
            priority: Message priority ('high' or 'normal')
            
        Returns:
            Dict with 'success_count', 'failure_count', and 'responses'
        """
        try:
            if not fcm_tokens:
                logger.warning("Cannot send multicast: empty token list")
                return {"success_count": 0, "failure_count": 0, "responses": []}
            
            # Build the multicast message
            message = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data or {},
                tokens=fcm_tokens,
                android=NotificationService._build_android_config(priority),
                apns=NotificationService._build_apns_config(title, body, priority),
            )
            
            # Send multicast asynchronously
            response = await messaging.send_each_for_multicast_async(message)
            
            logger.info(
                f"Multicast notification: {response.success_count} successful, "
                f"{response.failure_count} failed out of {len(fcm_tokens)} tokens"
            )
            
            return {
                "success_count": response.success_count,
                "failure_count": response.failure_count,
                "responses": response.responses
            }
            
        except Exception as e:
            logger.error(f"Error sending multicast notification: {e}")
            return {
                "success_count": 0,
                "failure_count": len(fcm_tokens),
                "responses": []
            }


# =========== Helper functions for common notification scenarios ===========

async def notify_provider_match(user_id: str, provider_name: str, category: str) -> bool:
    """Send notification when a service provider is matched."""
    return await NotificationService.send_to_user(
        user_id=user_id,
        title="Provider Found! 🎉",
        body=f"We found {provider_name} for your {category} request.",
        data={
            "type": "provider_match",
            "provider_name": provider_name,
            "category": category,
        }
    )


async def notify_request_completed(user_id: str) -> bool:
    """Send notification when user's request is completed."""
    return await NotificationService.send_to_user(
        user_id=user_id,
        title="Request Completed ✅",
        body="Your service request has been processed.",
        data={
            "type": "request_completed",
        }
    )


async def notify_conversation_update(user_id: str, message: str) -> bool:
    """Send notification for conversation updates."""
    return await NotificationService.send_to_user(
        user_id=user_id,
        title="New Message",
        body=message,
        data={
            "type": "conversation_update",
        }
    )
