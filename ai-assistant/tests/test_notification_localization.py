"""Tests for the notification localization package."""
import pytest

from ai_assistant.localization import NotificationStrings
from ai_assistant.localization.notifications_de import NotificationsDE
from ai_assistant.localization.notifications_en import NotificationsEN
from ai_assistant.localization.notification_strings import _LANGUAGE_MAP


class TestNotificationStringsResolver:
    """NotificationStrings resolves the right language class."""

    def test_english_is_default(self):
        strings = NotificationStrings('en')
        assert strings._msgs is NotificationsEN

    def test_german_resolves_to_de(self):
        strings = NotificationStrings('de')
        assert strings._msgs is NotificationsDE

    def test_unknown_language_falls_back_to_english(self):
        strings = NotificationStrings('fr')
        assert strings._msgs is NotificationsEN

    def test_empty_language_falls_back_to_english(self):
        strings = NotificationStrings('')
        assert strings._msgs is NotificationsEN


class TestStatusChangeStrings:
    """Properties for each status × role pair."""

    @pytest.mark.parametrize("lang", ["en", "de"])
    def test_accepted_seeker_has_title_and_body(self, lang):
        s = NotificationStrings(lang)
        assert s.accepted_seeker_title
        assert s.accepted_seeker_body

    @pytest.mark.parametrize("lang", ["en", "de"])
    def test_rejected_seeker_has_title_and_body(self, lang):
        s = NotificationStrings(lang)
        assert s.rejected_seeker_title
        assert s.rejected_seeker_body

    @pytest.mark.parametrize("lang", ["en", "de"])
    def test_service_provided_seeker_has_title_and_body(self, lang):
        s = NotificationStrings(lang)
        assert s.service_provided_seeker_title
        assert s.service_provided_seeker_body

    @pytest.mark.parametrize("lang", ["en", "de"])
    def test_cancelled_provider_has_title_and_body(self, lang):
        s = NotificationStrings(lang)
        assert s.cancelled_provider_title
        assert s.cancelled_provider_body

    @pytest.mark.parametrize("lang", ["en", "de"])
    def test_completed_provider_has_title_and_body(self, lang):
        s = NotificationStrings(lang)
        assert s.completed_provider_title
        assert s.completed_provider_body

    def test_english_and_german_strings_differ(self):
        """Sanity-check that translations are distinct."""
        en = NotificationStrings('en')
        de = NotificationStrings('de')
        assert en.accepted_seeker_title != de.accepted_seeker_title
        assert en.cancelled_provider_body != de.cancelled_provider_body


class TestNewRequestBody:
    """new_request_body() inserts the category correctly."""

    def test_with_category_in_english(self):
        body = NotificationStrings('en').new_request_body(category='Plumbing')
        assert 'Plumbing' in body
        assert '()' not in body

    def test_without_category_in_english(self):
        body = NotificationStrings('en').new_request_body()
        assert body.endswith('.')
        assert '()' not in body
        assert '{}' not in body

    def test_with_category_in_german(self):
        body = NotificationStrings('de').new_request_body(category='Klempner')
        assert 'Klempner' in body

    def test_without_category_in_german(self):
        body = NotificationStrings('de').new_request_body()
        assert '()' not in body

    def test_new_request_title_property(self):
        assert NotificationStrings('en').new_request_title
        assert NotificationStrings('de').new_request_title
        assert NotificationStrings('en').new_request_title != NotificationStrings('de').new_request_title


class TestLanguageMapCompleteness:
    """All registered language classes have identical attribute sets."""

    def _public_strings(self, cls: type) -> set[str]:
        return {
            k for k, v in vars(cls).items()
            if not k.startswith('_') and isinstance(v, str)
        }

    def test_all_languages_have_same_attributes(self):
        """Every language class must expose the same string attributes as EN."""
        en_attrs = self._public_strings(NotificationsEN)
        for lang_code, lang_cls in _LANGUAGE_MAP.items():
            if lang_cls is NotificationsEN:
                continue
            lang_attrs = self._public_strings(lang_cls)
            missing = en_attrs - lang_attrs
            extra = lang_attrs - en_attrs
            assert not missing, f"{lang_code} is missing attributes: {missing}"
            assert not extra, f"{lang_code} has unexpected extra attributes: {extra}"
