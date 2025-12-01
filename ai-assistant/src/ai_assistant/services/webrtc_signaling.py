"""
WebRTC Signaling Handler
Handles WebRTC signaling messages (offer, answer, ICE candidates).
"""
import logging
from aiortc import RTCSessionDescription

logger = logging.getLogger(__name__)


class WebRTCSignalingHandler:
    """Handles WebRTC signaling protocol messages."""

    @staticmethod
    async def handle_offer(peer_handler, offer_data: dict):
        """
        Handle WebRTC offer from client.
        
        Args:
            peer_handler: PeerConnectionHandler instance
            offer_data: Offer message data with 'sdp' and 'type'
        """
        try:
            logger.debug(f"Processing offer for {peer_handler.connection_id}")

            offer = RTCSessionDescription(
                sdp=offer_data['sdp'],
                type=offer_data['type']
            )

            await peer_handler.handle_offer(offer)

        except KeyError as e:
            logger.error(f"Missing required field in offer: {e}")
        except Exception as e:
            logger.error(f"Error handling offer: {e}", exc_info=True)

    @staticmethod
    async def handle_ice_candidate(peer_handler, candidate_data: dict):
        """
        Handle ICE candidate from client.
        
        Args:
            peer_handler: PeerConnectionHandler instance
            candidate_data: ICE candidate data
        """
        try:
            candidate = candidate_data.get('candidate')
            if candidate:
                logger.debug(f"Processing ICE candidate for {peer_handler.connection_id}")
                await peer_handler.handle_ice_candidate(candidate_data)
            else:
                logger.warning(
                    f"Received ice-candidate message without candidate data "
                    f"for {peer_handler.connection_id}"
                )

        except Exception as e:
            logger.error(f"Error handling ICE candidate: {e}", exc_info=True)

    @staticmethod
    async def route_message(peer_handler, message: dict):
        """
        Route signaling message to appropriate handler.
        
        Args:
            peer_handler: PeerConnectionHandler instance
            message: Message data with 'type' field
        """
        msg_type = message.get('type')
        logger.debug(f"Routing message type '{msg_type}' for {peer_handler.connection_id}")

        if msg_type == 'offer':
            await WebRTCSignalingHandler.handle_offer(peer_handler, message)
        elif msg_type == 'ice-candidate':
            await WebRTCSignalingHandler.handle_ice_candidate(peer_handler, message)
        else:
            logger.warning(f"Unknown message type: {msg_type}")
