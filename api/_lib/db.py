"""Postgres access layer (psycopg 3).

Serverless functions are short-lived and can start concurrently, so we open a
fresh connection per operation and let the Neon/Supabase connection *pooler*
handle reuse. Keep the ``DATABASE_URL`` pointed at the pooled endpoint.

Every row is returned as a plain ``dict`` (``dict_row`` row factory) so callers
don't depend on tuple ordering.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from typing import Any, Iterator, Optional

import psycopg
from psycopg.rows import dict_row

from _lib.config import settings


@contextmanager
def _conn() -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(settings.DATABASE_URL, row_factory=dict_row, autocommit=True)
    try:
        yield conn
    finally:
        conn.close()


# --- Users -----------------------------------------------------------------

def get_or_create_user(wa_number: str) -> dict[str, Any]:
    """Return the user row for a WhatsApp number, creating it on first contact.

    ``wa_number`` is the raw Twilio ``From`` value, e.g. ``whatsapp:+15551234567``.
    """
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE wa_number = %s", (wa_number,)
        ).fetchone()
        if row:
            return row
        return conn.execute(
            """
            INSERT INTO users (wa_number, daily_calorie_goal)
            VALUES (%s, %s)
            RETURNING *
            """,
            (wa_number, settings.DEFAULT_CALORIE_GOAL),
        ).fetchone()


def set_goal(user_id: int, goal: int) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE users SET daily_calorie_goal = %s WHERE id = %s", (goal, user_id)
        )


def set_active(user_id: int, active: bool) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE users SET active = %s WHERE id = %s", (active, user_id)
        )


def list_active_users() -> list[dict[str, Any]]:
    with _conn() as conn:
        return conn.execute("SELECT * FROM users WHERE active = true").fetchall()


# --- Food logs -------------------------------------------------------------

def log_food(
    user_id: int,
    description: str,
    calories: int,
    protein_g: Optional[float],
    carbs_g: Optional[float],
    fat_g: Optional[float],
    source: str,
) -> None:
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO food_logs
                (user_id, description, calories, protein_g, carbs_g, fat_g, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, description, calories, protein_g, carbs_g, fat_g, source),
        )


def totals_for_day(user_id: int, day: date) -> dict[str, Any]:
    """Aggregate calories + macros for a single UTC calendar day."""
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT
                COALESCE(SUM(calories), 0)   AS calories,
                COALESCE(SUM(protein_g), 0)  AS protein_g,
                COALESCE(SUM(carbs_g), 0)    AS carbs_g,
                COALESCE(SUM(fat_g), 0)      AS fat_g,
                COUNT(*)                     AS entries
            FROM food_logs
            WHERE user_id = %s AND created_at::date = %s
            """,
            (user_id, day),
        ).fetchone()
        return row


def clear_day(user_id: int, day: date) -> int:
    """Delete today's logs for a user; returns the number of rows removed."""
    with _conn() as conn:
        cur = conn.execute(
            "DELETE FROM food_logs WHERE user_id = %s AND created_at::date = %s",
            (user_id, day),
        )
        return cur.rowcount
