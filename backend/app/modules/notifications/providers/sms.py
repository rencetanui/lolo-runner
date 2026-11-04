import logging

import httpx

from app.core.config import settings

from .base import PermanentSendError, SendError

log = logging.getLogger(__name__)

ACCEPTED = {100, 101, 102}      # processed / sent / queued
PERMANENT = {403, 404, 406}     # invalid number / unsupported number type / blacklisted


class ConsoleSmsSender:
    """Dev only: log the SMS instead of sending it."""

    def send(self, *, to: str, message: str) -> str | None:
        log.info("SMS to=%s: %s", to, message)
        return None


class AfricasTalkingSender:
    def send(self, *, to: str, message: str) -> str | None:
        if not settings.at_api_key:
            raise SendError("Africa's Talking API key is not configured")
        base = (
            "https://api.sandbox.africastalking.com"
            if settings.at_env == "sandbox"
            else "https://api.africastalking.com"
        )
        data = {"username": settings.at_username, "to": to, "message": message}
        if settings.at_sender_id:
            data["from"] = settings.at_sender_id
        try:
            res = httpx.post(
                f"{base}/version1/messaging",
                data=data,
                headers={"apiKey": settings.at_api_key, "Accept": "application/json"},
                timeout=20,
            )
        except httpx.HTTPError as exc:
            raise SendError(f"Could not reach Africa's Talking: {exc}") from exc
        if res.status_code >= 400:
            raise SendError(f"Africa's Talking returned HTTP {res.status_code}")

        try:
            body = res.json()["SMSMessageData"]
            recipient = (body.get("Recipients") or [None])[0]
            if recipient is None:
                raise SendError(f"Africa's Talking: {body.get('Message', 'no recipients accepted')}")
            code = int(recipient["statusCode"])
        except (ValueError, KeyError, TypeError) as exc:
            raise SendError("Unexpected response from Africa's Talking") from exc

        if code in ACCEPTED:
            return recipient.get("messageId")
        error = f"Africa's Talking rejected the message ({code}: {recipient.get('status')})"
        raise (PermanentSendError if code in PERMANENT else SendError)(error)