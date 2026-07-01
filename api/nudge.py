"""Scheduled nudge sender, triggered by Vercel Cron.

Deployed as the serverless function at ``/api/nudge``. ``vercel.json`` defines the
cron schedule that hits this path. Because a cron endpoint is a public URL, we
require ``Authorization: Bearer $CRON_SECRET`` (Vercel Cron sends this header
automatically when ``CRON_SECRET`` is set as a project env var).

For each active user it generates a personalized encouragement + fitness tip and
sends it over WhatsApp via the Twilio REST API.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone

# Make the sibling ``_lib`` package importable no matter how this module is
# loaded — as ``api.nudge`` (local ``uvicorn api.nudge:app``) or when bundled by
# Vercel's Python builder, which runs the function from the ``api`` directory.
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from _lib import coach, db, twilio_client  # noqa: E402
from _lib.config import settings  # noqa: E402

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("nudge")

app = FastAPI()


def _authorized(request: Request) -> bool:
    auth = request.headers.get("authorization", "")
    return auth == f"Bearer {settings.CRON_SECRET}"


def _yesterday_summary(user_id: int, goal: int) -> str:
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    t = db.totals_for_day(user_id, yesterday)
    if t["entries"] == 0:
        return "No meals logged yesterday — today's a great day to start."
    return f"Yesterday you logged ~{t['calories']} kcal vs your {goal} goal."


def _run() -> dict:
    sent, failed = 0, 0
    for user in db.list_active_users():
        try:
            today = datetime.now(timezone.utc).date()
            today_total = db.totals_for_day(user["id"], today)["calories"]
            context = (
                f"goal {user['daily_calorie_goal']} kcal/day; "
                f"logged {today_total} kcal so far today"
            )
            message = coach.make_nudge(context)
            message += "\n\n" + _yesterday_summary(user["id"], user["daily_calorie_goal"])
            twilio_client.send(user["wa_number"], message)
            sent += 1
        except Exception:
            log.exception("Failed to send nudge to user %s", user["id"])
            failed += 1
    return {"sent": sent, "failed": failed}


@app.get("/api/nudge")
async def nudge(request: Request) -> JSONResponse:
    if not _authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    result = _run()
    log.info("Nudge run complete: %s", result)
    return JSONResponse(result)
