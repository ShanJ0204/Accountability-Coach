-- Schema for the WhatsApp accountability & health coach bot.
-- Apply once against your Postgres (Neon / Supabase) database:
--   psql "$DATABASE_URL" -f schema.sql

CREATE TABLE IF NOT EXISTS users (
    id                 SERIAL PRIMARY KEY,
    wa_number          TEXT UNIQUE NOT NULL,          -- Twilio "From", e.g. whatsapp:+15551234567
    display_name       TEXT,
    daily_calorie_goal INTEGER NOT NULL DEFAULT 2000,
    timezone           TEXT NOT NULL DEFAULT 'UTC',
    active             BOOLEAN NOT NULL DEFAULT true,  -- receives scheduled check-ins
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS food_logs (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    calories    INTEGER NOT NULL,
    protein_g   REAL,
    carbs_g     REAL,
    fat_g       REAL,
    source      TEXT NOT NULL CHECK (source IN ('image', 'text')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Fast lookups for per-day totals.
CREATE INDEX IF NOT EXISTS idx_food_logs_user_day
    ON food_logs (user_id, created_at);
