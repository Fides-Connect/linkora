"""Tests for SessionMode enum — RED phase."""
from ai_assistant.services.session_mode import SessionMode


class TestSessionMode:

    def test_voice_value_equals_string(self):
        assert SessionMode.VOICE == "voice"

    def test_text_value_equals_string(self):
        assert SessionMode.TEXT == "text"

    def test_is_string_subtype(self):
        # SessionMode(str, Enum) — every member IS a str
        assert isinstance(SessionMode.VOICE, str)
        assert isinstance(SessionMode.TEXT, str)

    def test_from_string_voice(self):
        assert SessionMode("voice") is SessionMode.VOICE

    def test_from_string_text(self):
        assert SessionMode("text") is SessionMode.TEXT

    def test_str_comparison_with_voice_string(self):
        # Both directions must hold so existing `== "voice"` guards work unchanged
        assert SessionMode.VOICE == "voice"
        assert "voice" == SessionMode.VOICE

    def test_str_comparison_with_text_string(self):
        assert SessionMode.TEXT == "text"
        assert "text" == SessionMode.TEXT

    def test_distinct_values(self):
        assert SessionMode.VOICE != SessionMode.TEXT

    def test_only_two_members(self):
        assert set(SessionMode) == {SessionMode.VOICE, SessionMode.TEXT}
