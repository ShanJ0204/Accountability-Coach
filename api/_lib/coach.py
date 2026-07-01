"""All Claude calls for the coach: vision calorie estimation, text food
classification/estimation, coaching chat, and scheduled nudges.

Estimates use structured outputs (``output_config.format``) so replies are small,
fast, and reliably parseable — which also keeps the inbound webhook inside Twilio's
~15s timeout. Model is configurable via ``COACH_MODEL`` (defaults to
``claude-opus-4-8`` for accuracy).
"""

from __future__ import annotations

import json
from typing import Any, Optional

import anthropic

from _lib.config import settings

_client: Optional[anthropic.Anthropic] = None


def _anthropic() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


# Shared JSON schema for a calorie/macro estimate. ``is_food`` lets a single call
# distinguish "the user described a meal" from "the user is just chatting".
_ESTIMATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "is_food": {
            "type": "boolean",
            "description": "True only if the input describes food/drink actually eaten.",
        },
        "description": {
            "type": "string",
            "description": "Short label for the meal, e.g. 'Grilled chicken salad'.",
        },
        "calories": {"type": "integer", "description": "Best estimate of total kcal."},
        "protein_g": {"type": "number"},
        "carbs_g": {"type": "number"},
        "fat_g": {"type": "number"},
        "confidence": {
            "type": "string",
            "enum": ["low", "medium", "high"],
            "description": "How confident the estimate is.",
        },
    },
    "required": [
        "is_food",
        "description",
        "calories",
        "protein_g",
        "carbs_g",
        "fat_g",
        "confidence",
    ],
    "additionalProperties": False,
}

_ESTIMATE_SYSTEM = (
    "You are a nutrition estimator for a health-coaching app. Estimate calories and "
    "macronutrients for food a user reports eating. Assume a normal single serving "
    "unless the user specifies a quantity. Estimates are approximate; use the "
    "confidence field honestly. If the input is not about food actually eaten "
    "(a greeting, a question, small talk), set is_food=false and leave the numbers 0."
)


def _parse_estimate(response: anthropic.types.Message) -> dict[str, Any]:
    """Pull the JSON object out of a structured-output response."""
    text = next((b.text for b in response.content if b.type == "text"), "{}")
    return json.loads(text)


def estimate_from_image(image_b64: str, media_type: str, caption: str = "") -> dict[str, Any]:
    """Estimate calories/macros from a food photo (base64-encoded).

    ``caption`` is any text the user sent alongside the image (e.g. "large portion").
    """
    prompt = "Estimate the calories and macros for the food in this image."
    if caption.strip():
        prompt += f" The user added: {caption.strip()!r}."

    response = _anthropic().messages.create(
        model=settings.MODEL,
        max_tokens=500,
        system=_ESTIMATE_SYSTEM,
        output_config={"format": {"type": "json_schema", "schema": _ESTIMATE_SCHEMA}},
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )
    return _parse_estimate(response)


def estimate_from_text(text: str) -> dict[str, Any]:
    """Classify a text message and, if it's food, estimate calories/macros."""
    response = _anthropic().messages.create(
        model=settings.MODEL,
        max_tokens=500,
        system=_ESTIMATE_SYSTEM,
        output_config={"format": {"type": "json_schema", "schema": _ESTIMATE_SCHEMA}},
        messages=[{"role": "user", "content": text}],
    )
    return _parse_estimate(response)


_COACH_SYSTEM = (
    "You are a warm, encouraging accountability and health coach chatting with a user "
    "over WhatsApp. Keep replies short (1-3 sentences), friendly, and practical. You "
    "help with fitness, nutrition, habits, and motivation. You are not a doctor; for "
    "medical concerns, gently suggest seeing a professional. Do not use markdown "
    "formatting — this is a plain-text chat."
)


def chat_reply(user_text: str, context: str = "") -> str:
    """Generate a coaching reply to a non-food chat message."""
    content = user_text
    if context:
        content = f"[context: {context}]\n\n{user_text}"
    response = _anthropic().messages.create(
        model=settings.MODEL,
        max_tokens=400,
        system=_COACH_SYSTEM,
        messages=[{"role": "user", "content": content}],
    )
    return next((b.text for b in response.content if b.type == "text"), "").strip()


def make_nudge(context: str) -> str:
    """Generate a short, varied encouragement + fitness tip for a scheduled nudge.

    ``context`` carries per-user info (e.g. calories logged so far) so the message
    is relevant rather than generic.
    """
    response = _anthropic().messages.create(
        model=settings.MODEL,
        max_tokens=300,
        system=(
            "You write a single short WhatsApp check-in for a user of a health-coaching "
            "app: one line of genuine encouragement plus one concrete, actionable fitness "
            "or nutrition tip. Vary your wording and topics so daily messages feel fresh. "
            "Keep it under ~40 words, warm, plain text, no markdown."
        ),
        messages=[{"role": "user", "content": f"Write today's check-in. Context: {context}"}],
    )
    return next((b.text for b in response.content if b.type == "text"), "").strip()
