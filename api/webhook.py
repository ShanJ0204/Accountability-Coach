"""Twilio inbound-message webhook.

Deployed by Vercel as the serverless function at ``/api/webhook``. Configure this
URL as the "When a message comes in" webhook (HTTP POST) for your Twilio WhatsApp
number / sandbox.

Flow: verify Twilio's signature → parse the form → route via ``handlers`` → return
TwiML so Twilio renders the reply back to the user.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse

from _lib import twilio_client
from _lib.handlers import handle_message

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("webhook")

app = FastAPI()


def _twiml(message: str) -> Response:
    """Wrap a reply string in a minimal TwiML <Message> response."""
    from xml.sax.saxutils import escape

    body = f"<?xml version='1.0' encoding='UTF-8'?><Response><Message>{escape(message)}</Message></Response>"
    return Response(content=body, media_type="application/xml")


def _public_url(request: Request) -> str:
    """Reconstruct the exact URL Twilio signed, honoring Vercel's proxy headers."""
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    return f"{proto}://{host}{request.url.path}"


@app.get("/api/webhook")
async def health() -> PlainTextResponse:
    return PlainTextResponse("ok")


@app.post("/api/webhook")
async def inbound(request: Request) -> Response:
    form = await request.form()
    params = {k: str(v) for k, v in form.items()}

    signature = request.headers.get("X-Twilio-Signature")
    if not twilio_client.verify_signature(_public_url(request), params, signature):
        log.warning("Rejected inbound message: invalid Twilio signature")
        return Response(status_code=403, content="invalid signature")

    from_number = params.get("From", "")
    body = params.get("Body", "")
    num_media = int(params.get("NumMedia", "0") or "0")
    media_url = params.get("MediaUrl0") if num_media > 0 else None
    media_content_type = params.get("MediaContentType0") if num_media > 0 else None

    try:
        reply = handle_message(from_number, body, media_url, media_content_type)
    except Exception:  # keep the user informed; never 500 back to Twilio
        log.exception("Failed to handle inbound message")
        reply = "Sorry, something went wrong on my end. Please try again in a moment."

    return _twiml(reply)
