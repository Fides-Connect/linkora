"""English push-notification strings.

Each attribute name **must** match the corresponding attribute in every other
language file (e.g. ``notifications_de.py``).  The ``NotificationStrings``
resolver picks a language class at runtime and accesses attributes by name, so
a missing or misspelled attribute will raise ``AttributeError``.

Dynamic strings use ``str.format_map`` placeholders documented per attribute.
"""


class NotificationsEN:
    """Static English notification string constants."""

    # ── Service-request status changes ────────────────────────────────────────

    # accepted (seeker)
    accepted_seeker_title = "Request Accepted ✅"
    accepted_seeker_body = "A provider has accepted your service request."

    # rejected (seeker)
    rejected_seeker_title = "Request Declined ❌"
    rejected_seeker_body = "Unfortunately your service request was declined."

    # serviceProvided (seeker)
    service_provided_seeker_title = "Service Completed 🎉"
    service_provided_seeker_body = (
        "The provider marked the service as done. Please confirm payment."
    )

    # cancelled (provider)
    cancelled_provider_title = "Request Cancelled"
    cancelled_provider_body = "The customer has cancelled the service request."

    # completed (provider)
    completed_provider_title = "Payment Confirmed 💰"
    completed_provider_body = "The customer confirmed payment. Thank you!"

    # ── New service request ────────────────────────────────────────────────────
    # Placeholder ``{category_suffix}`` is replaced with `` (Category)`` or
    # an empty string when no category is set.

    new_request_title = "New Service Request 🔔"
    new_request_body = "You have received a new service request{category_suffix}."
