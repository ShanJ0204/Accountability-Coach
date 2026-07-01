"""Central configuration, sourced from environment variables.

Import ``settings`` and read attributes off it. Missing *required* values raise a
clear error the first time they're accessed rather than failing deep inside an API
call. ``.env`` is loaded automatically for local development.
"""

from __future__ import annotations

import os
from functools import cached_property

try:  # local dev convenience; on Vercel the env vars are injected directly
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv not installed in prod image — that's fine
    pass


class MissingConfig(RuntimeError):
    """Raised when a required environment variable is not set."""


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise MissingConfig(
            f"Environment variable {name!r} is required but not set. "
            f"See .env.example for the full list."
        )
    return value


class Settings:
    # --- Claude ---
    # Default to the accuracy-leaning model. Override with COACH_MODEL to swap
    # (e.g. claude-sonnet-5) without touching code.
    MODEL: str = os.environ.get("COACH_MODEL", "claude-opus-4-8")

    # --- Nutrition defaults ---
    DEFAULT_CALORIE_GOAL: int = int(os.environ.get("DEFAULT_CALORIE_GOAL", "2000"))

    # --- Twilio WhatsApp sender, e.g. "whatsapp:+14155238886" (sandbox) ---
    @cached_property
    def TWILIO_WHATSAPP_FROM(self) -> str:
        return _required("TWILIO_WHATSAPP_FROM")

    @cached_property
    def TWILIO_ACCOUNT_SID(self) -> str:
        return _required("TWILIO_ACCOUNT_SID")

    @cached_property
    def TWILIO_AUTH_TOKEN(self) -> str:
        return _required("TWILIO_AUTH_TOKEN")

    # --- Anthropic ---
    @cached_property
    def ANTHROPIC_API_KEY(self) -> str:
        return _required("ANTHROPIC_API_KEY")

    # --- Postgres (Neon / Supabase pooled connection string) ---
    @cached_property
    def DATABASE_URL(self) -> str:
        return _required("DATABASE_URL")

    # --- Cron protection ---
    @cached_property
    def CRON_SECRET(self) -> str:
        return _required("CRON_SECRET")


settings = Settings()
