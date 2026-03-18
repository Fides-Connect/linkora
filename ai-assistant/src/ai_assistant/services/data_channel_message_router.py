"""DataChannelMessageRouter — dispatch table for DataChannel messages.

Replaces the ``if/elif`` chain in ``PeerConnectionHandler``'s ``on_message``
closure.  New message types are a single ``register()`` call.
"""
import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


class DataChannelMessageRouter:
    """Routes incoming DataChannel messages to registered handlers.

    Usage::

        router = DataChannelMessageRouter()
        router.register("text-input", self._on_dc_text_input)
        router.register("mode-switch", self._on_dc_mode_switch)

        # inside on_message:
        router.dispatch(json.loads(message))
    """

    def __init__(self) -> None:
        self._handlers: dict[str, Callable[[dict], None]] = {}

    def register(self, msg_type: str, handler: Callable[[dict], None]) -> None:
        """Register *handler* for *msg_type*, replacing any previous handler."""
        self._handlers[msg_type] = handler

    def dispatch(self, data: dict) -> None:
        """Call the handler registered for ``data["type"]``.

        Logs a warning for unknown types; does not propagate handler exceptions
        (callers should not depend on error handling behaviour of individual
        handlers).
        """
        msg_type = data.get("type")
        handler = self._handlers.get(msg_type)
        if handler is None:
            logger.warning("DataChannelMessageRouter: unknown message type %r", msg_type)
            return
        try:
            handler(data)
        except Exception as exc:
            logger.error(
                "DataChannelMessageRouter: handler for %r raised: %s",
                msg_type,
                exc,
                exc_info=True,
            )
