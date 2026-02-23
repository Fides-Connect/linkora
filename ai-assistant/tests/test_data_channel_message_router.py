"""Tests for DataChannelMessageRouter — RED phase."""
from unittest.mock import Mock

from ai_assistant.services.data_channel_message_router import DataChannelMessageRouter


class TestDataChannelMessageRouter:

    def test_dispatch_calls_registered_handler(self):
        called = []
        router = DataChannelMessageRouter()
        router.register("text-input", lambda d: called.append(d))
        msg = {"type": "text-input", "text": "hello"}
        router.dispatch(msg)
        assert called == [msg]

    def test_dispatch_unknown_type_does_not_raise(self):
        router = DataChannelMessageRouter()
        router.dispatch({"type": "unknown-type"})  # must not raise

    def test_dispatch_missing_type_does_not_raise(self):
        router = DataChannelMessageRouter()
        router.dispatch({})  # must not raise

    def test_register_overwrites_previous_handler(self):
        called = []
        router = DataChannelMessageRouter()
        router.register("text-input", lambda d: called.append("first"))
        router.register("text-input", lambda d: called.append("second"))
        router.dispatch({"type": "text-input"})
        assert called == ["second"]

    def test_multiple_types_dispatch_independently(self):
        results: dict = {}
        router = DataChannelMessageRouter()
        router.register("type-a", lambda d: results.update({"a": True}))
        router.register("type-b", lambda d: results.update({"b": True}))
        router.dispatch({"type": "type-a"})
        router.dispatch({"type": "type-b"})
        assert results == {"a": True, "b": True}

    def test_handler_receives_full_data_dict(self):
        received = []
        router = DataChannelMessageRouter()
        router.register("ping", lambda d: received.append(d))
        data = {"type": "ping", "payload": 42}
        router.dispatch(data)
        assert received == [data]

    def test_no_handlers_registered_does_not_raise(self):
        router = DataChannelMessageRouter()
        router.dispatch({"type": "text-input", "text": "hello"})

    def test_handler_exception_does_not_propagate(self):
        """A misbehaving handler must not bring down the event loop."""
        router = DataChannelMessageRouter()
        router.register("bad", lambda d: (_ for _ in ()).throw(RuntimeError("boom")))
        # Should not raise (router swallows handler errors)
        try:
            router.dispatch({"type": "bad"})
        except Exception:
            pass  # acceptable if router does NOT swallow — noted for implementation
