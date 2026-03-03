"""Localization package for push notification strings.

Structure mirrors the Flutter ConnectX app:
  notifications_en.py  →  MessagesEN  (static string constants)
  notifications_de.py  →  MessagesDE  (static string constants)
  notification_strings.py  →  NotificationStrings  (resolver, like AppLocalizations)

To add a new language:
  1. Create ``notifications_<code>.py`` with a class that has the same
     attribute names as ``NotificationsEN``.
  2. Register it in ``notification_strings._LANGUAGE_MAP``.
"""
from .notification_strings import NotificationStrings

__all__ = ["NotificationStrings"]
