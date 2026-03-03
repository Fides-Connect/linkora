"""German push-notification strings.

Attribute names must exactly match those in ``notifications_en.py``.
"""


class NotificationsDE:
    """Static German notification string constants."""

    # ── Service-request status changes ────────────────────────────────────────

    # accepted (seeker)
    accepted_seeker_title = "Anfrage akzeptiert ✅"
    accepted_seeker_body = "Ein Anbieter hat Ihre Serviceanfrage angenommen."

    # rejected (seeker)
    rejected_seeker_title = "Anfrage abgelehnt ❌"
    rejected_seeker_body = "Leider wurde Ihre Serviceanfrage abgelehnt."

    # serviceProvided (seeker)
    service_provided_seeker_title = "Service abgeschlossen 🎉"
    service_provided_seeker_body = (
        "Der Anbieter hat den Service als erledigt markiert. "
        "Bitte bestätigen Sie die Zahlung."
    )

    # cancelled (provider)
    cancelled_provider_title = "Anfrage storniert"
    cancelled_provider_body = "Der Kunde hat die Serviceanfrage storniert."

    # completed (provider)
    completed_provider_title = "Zahlung bestätigt 💰"
    completed_provider_body = (
        "Der Kunde hat die Zahlung bestätigt. Vielen Dank!"
    )

    # ── New service request ────────────────────────────────────────────────────

    new_request_title = "Neue Serviceanfrage 🔔"
    new_request_body = "Sie haben eine neue Serviceanfrage erhalten{category_suffix}."
