import json

from flask import current_app


def _normalize_whatsapp_number(raw_number):
    value = (raw_number or "").strip()
    if not value:
        return ""
    if value.startswith("whatsapp:"):
        return value
    if not value.startswith("+"):
        value = f"+{value}"
    return f"whatsapp:{value}"


def _get_twilio_context(to_number):
    if not current_app.config.get("ENABLE_TWILIO_WHATSAPP", False):
        return None

    account_sid = (current_app.config.get("TWILIO_ACCOUNT_SID") or "").strip()
    auth_token = (current_app.config.get("TWILIO_AUTH_TOKEN") or "").strip()
    from_number = _normalize_whatsapp_number(current_app.config.get("TWILIO_WHATSAPP_FROM_NUMBER", ""))
    to_whatsapp = _normalize_whatsapp_number(to_number)
    if not account_sid or not auth_token or not from_number or not to_whatsapp:
        current_app.logger.warning(
            "WhatsApp message not sent: missing Twilio credentials or from/to number"
        )
        return None

    try:
        from twilio.rest import Client
    except ImportError:
        current_app.logger.error("Twilio SDK is not installed. Add 'twilio' to requirements.")
        return None

    return {
        "client": Client(account_sid, auth_token),
        "from_number": from_number,
        "to_whatsapp": to_whatsapp,
    }


def send_whatsapp_template(to_number, content_sid, content_variables):
    if not content_sid:
        current_app.logger.warning("WhatsApp template not sent: content SID is missing")
        return False

    context = _get_twilio_context(to_number)
    if not context:
        return False

    try:
        message = context["client"].messages.create(
            from_=context["from_number"],
            content_sid=content_sid,
            content_variables=json.dumps(content_variables or {}),
            to=context["to_whatsapp"],
        )
        current_app.logger.info("Twilio WhatsApp message queued: %s", getattr(message, "sid", "unknown"))
        return True
    except Exception as exc:  # noqa: BLE001
        current_app.logger.error("Twilio WhatsApp template send failed: %s", exc)
        return False


def send_whatsapp_text(to_number, body):
    if not body:
        return False

    context = _get_twilio_context(to_number)
    if not context:
        return False

    try:
        message = context["client"].messages.create(
            from_=context["from_number"],
            body=body,
            to=context["to_whatsapp"],
        )
        current_app.logger.info("Twilio WhatsApp text queued: %s", getattr(message, "sid", "unknown"))
        return True
    except Exception as exc:  # noqa: BLE001
        current_app.logger.error("Twilio WhatsApp text send failed: %s", exc)
        return False
