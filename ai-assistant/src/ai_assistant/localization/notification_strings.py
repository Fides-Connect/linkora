"""Notification string resolver — the Python equivalent of ``AppLocalizations``.

Usage::

    strings = NotificationStrings('de')
    title = strings.accepted_seeker_title
    body  = strings.new_request_body(category='Klempner')

Adding a new language
---------------------
1. Create ``notifications_<code>.py`` with a class that mirrors
   ``NotificationsEN`` attribute-for-attribute.
2. Add an entry to ``_LANGUAGE_MAP`` below.

No other file needs to change.
"""
from __future__ import annotations

from .notifications_de import NotificationsDE
from .notifications_en import NotificationsEN

_NotificationsClass = type[NotificationsDE] | type[NotificationsEN]

# Map ISO 639-1 language code → string-constant class.
# Unknown codes fall back to English (see ``NotificationStrings.__init__``).
_LANGUAGE_MAP: dict[str, _NotificationsClass] = {
    "en": NotificationsEN,
    "de": NotificationsDE,
}


class NotificationStrings:
    """Resolves notification strings for a given language code.

    Mirrors the Flutter ``AppLocalizations`` pattern: instantiate with a
    language code, then access properties by name.  Falls back to English for
    any unsupported language code.
    """

    def __init__(self, language: str) -> None:
        # Normalize inputs like "DE" or " de " so callers don't need to
        # guarantee formatting before constructing NotificationStrings.
        normalized_language = (language or "").strip().lower()
        self._msgs: _NotificationsClass = _LANGUAGE_MAP.get(normalized_language, NotificationsEN)

    # ── Service-request status-change strings ─────────────────────────────────

    @property
    def accepted_seeker_title(self) -> str:
        return self._msgs.accepted_seeker_title

    @property
    def accepted_seeker_body(self) -> str:
        return self._msgs.accepted_seeker_body

    @property
    def rejected_seeker_title(self) -> str:
        return self._msgs.rejected_seeker_title

    @property
    def rejected_seeker_body(self) -> str:
        return self._msgs.rejected_seeker_body

    @property
    def service_provided_seeker_title(self) -> str:
        return self._msgs.service_provided_seeker_title

    @property
    def service_provided_seeker_body(self) -> str:
        return self._msgs.service_provided_seeker_body

    @property
    def cancelled_provider_title(self) -> str:
        return self._msgs.cancelled_provider_title

    @property
    def cancelled_provider_body(self) -> str:
        return self._msgs.cancelled_provider_body

    @property
    def completed_provider_title(self) -> str:
        return self._msgs.completed_provider_title

    @property
    def completed_provider_body(self) -> str:
        return self._msgs.completed_provider_body

    # ── New service request ────────────────────────────────────────────────────

    @property
    def new_request_title(self) -> str:
        return self._msgs.new_request_title

    def new_request_body(self, category: str = "") -> str:
        """Return the new-request notification body with an optional category.

        The category is appended as `` (Category)`` when provided.
        """
        suffix = f" ({category})" if category else ""
        return self._msgs.new_request_body.format(category_suffix=suffix)
