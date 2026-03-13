import json
from urllib import error, request

from flask import current_app


def send_email(to_email, subject, text_body, html_body=None):
    if not current_app.config.get("ENABLE_EMAIL_NOTIFICATIONS", True):
        return False

    from_email = current_app.config.get("FROM_EMAIL", "").strip()
    provider = (current_app.config.get("EMAIL_PROVIDER") or "resend").strip().lower()
    if not from_email:
        current_app.logger.warning("Email not sent: FROM_EMAIL is missing")
        return False

    if provider == "sendgrid":
        return _send_via_sendgrid(
            to_email=to_email,
            from_email=from_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )
    return _send_via_resend(
        to_email=to_email,
        from_email=from_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )


def _send_via_resend(to_email, from_email, subject, text_body, html_body=None):
    api_key = current_app.config.get("RESEND_API_KEY", "").strip()
    if not api_key:
        current_app.logger.warning("Email not sent: RESEND_API_KEY is missing")
        return False

    payload = {
        "from": from_email,
        "to": [to_email],
        "subject": subject,
        "text": text_body,
    }
    if html_body:
        payload["html"] = html_body

    req = request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except error.HTTPError as exc:
        current_app.logger.error("Resend API HTTP error: %s", exc)
    except error.URLError as exc:
        current_app.logger.error("Resend API connection error: %s", exc)

    return False


def _send_via_sendgrid(to_email, from_email, subject, text_body, html_body=None):
    api_key = current_app.config.get("SENDGRID_API_KEY", "").strip()
    if not api_key:
        current_app.logger.warning("Email not sent: SENDGRID_API_KEY is missing")
        return False

    content = [{"type": "text/plain", "value": text_body}]
    if html_body:
        content.append({"type": "text/html", "value": html_body})

    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": from_email},
        "subject": subject,
        "content": content,
    }

    req = request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except error.HTTPError as exc:
        current_app.logger.error("SendGrid API HTTP error: %s", exc)
    except error.URLError as exc:
        current_app.logger.error("SendGrid API connection error: %s", exc)

    return False
