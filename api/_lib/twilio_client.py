"""Twilio WhatsApp helpers: inbound signature verification, media fetch, outbound send."""

from __future__ import annotations

import base64
from typing import Optional

import requests
from twilio.request_validator import RequestValidator
from twilio.rest import Client

from _lib.config import settings


def verify_signature(url: str, params: dict[str, str], signature: Optional[str]) -> bool:
    """Validate Twilio's ``X-Twilio-Signature`` for an inbound webhook request.

    ``url`` must be the exact public URL Twilio POSTed to (scheme + host + path,
    no trailing changes) and ``params`` the full POST form dict.
    """
    if not signature:
        return False
    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    return validator.validate(url, params, signature)


def fetch_media(media_url: str) -> tuple[bytes, str]:
    """Download an inbound media file. Twilio media URLs require HTTP Basic auth.

    Returns ``(content_bytes, content_type)``.
    """
    resp = requests.get(
        media_url,
        auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
        timeout=15,
    )
    resp.raise_for_status()
    content_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
    return resp.content, content_type


def image_to_base64(content: bytes) -> str:
    return base64.standard_b64encode(content).decode("utf-8")


_client: Optional[Client] = None


def _rest_client() -> Client:
    global _client
    if _client is None:
        _client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    return _client


def send(to: str, body: str) -> None:
    """Send an outbound WhatsApp message via the Twilio REST API.

    Used for scheduled nudges. ``to`` should be a ``whatsapp:+E164`` address.
    """
    _rest_client().messages.create(
        from_=settings.TWILIO_WHATSAPP_FROM,
        to=to,
        body=body,
    )
