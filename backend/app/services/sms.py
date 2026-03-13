import base64
from urllib.parse import urlencode
from urllib import error, request

from flask import current_app


def send_sms(to_number, message):
    account_sid = (current_app.config.get("TWILIO_ACCOUNT_SID") or "").strip()
    auth_token = (current_app.config.get("TWILIO_AUTH_TOKEN") or "").strip()
    from_number = (current_app.config.get("TWILIO_FROM_NUMBER") or "").strip()

    if not account_sid or not auth_token or not from_number:
        current_app.logger.warning(
            "SMS not sent: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, or TWILIO_FROM_NUMBER is missing"
        )
        return False

    # Twilio's Messages API expects x-www-form-urlencoded payload.
    body = urlencode({"From": from_number, "To": to_number, "Body": message})
    auth_bytes = f"{account_sid}:{auth_token}".encode("utf-8")
    auth_header = base64.b64encode(auth_bytes).decode("ascii")

    req = request.Request(
        f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
        data=body.encode("utf-8"),
        headers={
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except error.HTTPError as exc:
        current_app.logger.error("Twilio API HTTP error: %s", exc)
    except error.URLError as exc:
        current_app.logger.error("Twilio API connection error: %s", exc)

    return False
