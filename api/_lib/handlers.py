"""Inbound-message routing: turn a parsed Twilio message into a reply string.

Kept separate from the FastAPI endpoint so it can be unit-tested and reused. The
endpoint is responsible only for HTTP concerns (signature check, form parsing,
TwiML rendering); everything else lives here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from _lib import coach, db, twilio_client

# --- reply formatting ------------------------------------------------------


def _goal_line(user: dict[str, Any], total_cals: int) -> str:
    goal = user["daily_calorie_goal"]
    remaining = goal - total_cals
    if remaining >= 0:
        return f"Today: {total_cals}/{goal} kcal ({remaining} left)."
    return f"Today: {total_cals}/{goal} kcal ({-remaining} over goal)."


def _format_estimate_reply(user: dict[str, Any], est: dict[str, Any], total_cals: int) -> str:
    conf = est.get("confidence", "medium")
    macros = (
        f"P {round(est['protein_g'])}g · C {round(est['carbs_g'])}g · F {round(est['fat_g'])}g"
    )
    return (
        f"Logged: {est['description']} — ~{est['calories']} kcal ({conf} confidence)\n"
        f"{macros}\n"
        f"{_goal_line(user, total_cals)}\n"
        f"(estimate — adjust anytime)"
    )


def _today() -> "datetime.date":
    return datetime.now(timezone.utc).date()


# --- command handling ------------------------------------------------------


def _handle_command(user: dict[str, Any], text: str) -> Optional[str]:
    """Return a reply if ``text`` is a recognized command, else ``None``."""
    lowered = text.strip().lower()

    if lowered in ("total", "today", "summary"):
        t = db.totals_for_day(user["id"], _today())
        if t["entries"] == 0:
            return "No food logged yet today. Send a photo or describe a meal to start."
        return (
            f"Today so far ({t['entries']} entries):\n"
            f"~{t['calories']} kcal · P {round(t['protein_g'])}g · "
            f"C {round(t['carbs_g'])}g · F {round(t['fat_g'])}g\n"
            f"{_goal_line(user, t['calories'])}"
        )

    if lowered.startswith("goal"):
        parts = lowered.split()
        if len(parts) == 2 and parts[1].isdigit():
            db.set_goal(user["id"], int(parts[1]))
            return f"Daily calorie goal set to {int(parts[1])} kcal. You've got this!"
        return "To set your goal, send: goal 1800"

    if lowered == "reset":
        removed = db.clear_day(user["id"], _today())
        return f"Cleared {removed} entr{'y' if removed == 1 else 'ies'} for today. Fresh start!"

    if lowered == "stop":
        db.set_active(user["id"], False)
        return "You'll no longer receive check-ins. Send 'start' anytime to resume."

    if lowered == "start":
        db.set_active(user["id"], True)
        return "Welcome back! Daily check-ins are on. Send a meal photo to log food."

    if lowered in ("help", "menu", "?"):
        return (
            "I'm your health coach. You can:\n"
            "• Send a food photo → I estimate calories\n"
            "• Describe a meal → I log it\n"
            "• 'total' → today's summary\n"
            "• 'goal 1800' → set daily calorie goal\n"
            "• 'reset' → clear today's log\n"
            "• 'stop' / 'start' → toggle daily check-ins\n"
            "• Ask me anything about fitness or nutrition!"
        )

    return None


# --- main entry point ------------------------------------------------------


def handle_message(
    from_number: str,
    body: str,
    media_url: Optional[str],
    media_content_type: Optional[str],
) -> str:
    """Process one inbound WhatsApp message and return the reply text."""
    user = db.get_or_create_user(from_number)

    # 1. Food photo → vision estimate
    if media_url and (media_content_type or "").startswith("image/"):
        content, ctype = twilio_client.fetch_media(media_url)
        est = coach.estimate_from_image(
            twilio_client.image_to_base64(content), ctype, caption=body or ""
        )
        if not est.get("is_food"):
            return (
                "I couldn't spot a meal in that image. Try a clear photo of your food, "
                "or just describe what you ate."
            )
        db.log_food(
            user["id"], est["description"], est["calories"],
            est["protein_g"], est["carbs_g"], est["fat_g"], source="image",
        )
        total = db.totals_for_day(user["id"], _today())["calories"]
        return _format_estimate_reply(user, est, total)

    text = (body or "").strip()
    if not text:
        return "Send me a food photo, describe a meal, or say 'help' to see what I can do."

    # 2. Explicit commands
    command_reply = _handle_command(user, text)
    if command_reply is not None:
        return command_reply

    # 3. Text that might be food → classify + estimate in one call
    est = coach.estimate_from_text(text)
    if est.get("is_food"):
        db.log_food(
            user["id"], est["description"], est["calories"],
            est["protein_g"], est["carbs_g"], est["fat_g"], source="text",
        )
        total = db.totals_for_day(user["id"], _today())["calories"]
        return _format_estimate_reply(user, est, total)

    # 4. Otherwise: coaching chat
    t = db.totals_for_day(user["id"], _today())
    context = f"user has logged {t['calories']} kcal today, goal {user['daily_calorie_goal']}"
    return coach.chat_reply(text, context=context)
