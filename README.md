# Accountability Coach — WhatsApp Health Bot

A WhatsApp chatbot that acts as an **accountability and health coach**. It:

- 📸 **Tracks calories from food photos** — send a picture of your meal and it estimates
  calories + macros (protein / carbs / fat) using Claude's vision model.
- ✍️ **Logs meals from text** — "two eggs and toast with butter" gets logged the same way.
- 💬 **Coaches you** — ask anything about fitness, nutrition, habits, or motivation.
- 🔔 **Sends daily check-ins** — a scheduled nudge with encouragement + a fitness tip,
  personalized with your recent intake.

Built with **Python + FastAPI**, deployed as **Vercel serverless functions** with
**Vercel Cron** for the scheduled nudges, **Twilio** for WhatsApp, **Claude** for
vision + coaching, and **Postgres** (Neon/Supabase) for storage.

> ⚠️ **Health disclaimer:** Calorie and macro figures are AI *estimates*, not medical
> advice. They're meant for casual self-tracking. For dietary or medical decisions,
> consult a qualified professional.

---

## How it works

```
WhatsApp user
     │  (text / photo)
     ▼
Twilio  ──POST──►  /api/webhook  (FastAPI on Vercel)
                        │
                        ├─ verify Twilio signature
                        ├─ photo?  → fetch media → Claude vision → estimate → log
                        ├─ command? (total / goal / reset / stop / start)
                        ├─ food text? → Claude classify+estimate → log
                        └─ else → Claude coaching reply
                        │
                        ▼
                    Postgres (users, food_logs)

Vercel Cron ──GET──►  /api/nudge  → Claude nudge → Twilio REST → WhatsApp
```

Shared code lives in `api/_lib/` (the leading underscore stops Vercel from treating
those modules as their own functions).

### Chat commands

| Send | Effect |
|---|---|
| a food photo | estimate + log calories |
| a meal description | estimate + log calories |
| `total` / `today` | today's running summary |
| `goal 1800` | set your daily calorie goal |
| `reset` | clear today's log |
| `stop` / `start` | turn daily check-ins off / on |
| `help` | show the command menu |
| anything else | coaching conversation |

---

## Setup

### 1. Prerequisites

- A **Twilio** account with the [WhatsApp sandbox](https://www.twilio.com/docs/whatsapp/sandbox)
  enabled (or an approved WhatsApp sender for production).
- An **Anthropic** API key.
- A **Postgres** database — [Neon](https://neon.tech) or [Supabase](https://supabase.com)
  both have free tiers. Use the **pooled** connection string.

### 2. Install & configure

```bash
pip install -r requirements.txt
cp .env.example .env      # then fill in the values
```

Apply the database schema:

```bash
psql "$DATABASE_URL" -f schema.sql
```

### 3. Smoke-test the vision path (no WhatsApp needed)

```bash
python scripts/smoke.py path/to/food_photo.jpg
# or
python scripts/smoke.py --text "grilled chicken salad with olive oil"
```

You should get a JSON estimate like:

```json
{ "is_food": true, "description": "Grilled chicken salad",
  "calories": 420, "protein_g": 38, "carbs_g": 12, "fat_g": 24,
  "confidence": "medium" }
```

### 4. Run locally end-to-end

```bash
uvicorn api.webhook:app --reload --port 8000
```

Expose it with a tunnel (e.g. `ngrok http 8000`), then in the Twilio Console set your
WhatsApp sandbox's **"When a message comes in"** webhook to
`https://<your-tunnel>/api/webhook` (HTTP POST). Join the sandbox from your phone and:

- send a **food photo** → expect a calorie estimate + today's total
- send **`total`** → expect a summary
- send **`goal 1800`** → expect a confirmation
- ask **"any tips for staying motivated?"** → expect a coaching reply

Test the nudge endpoint:

```bash
curl -H "Authorization: Bearer $CRON_SECRET" http://localhost:8000/api/nudge
```

### 5. Deploy to Vercel

```bash
vercel            # first deploy / link project
vercel --prod     # production deploy
```

Then:

1. In **Vercel → Project → Settings → Environment Variables**, add every variable from
   `.env.example` (`ANTHROPIC_API_KEY`, `TWILIO_*`, `DATABASE_URL`, `CRON_SECRET`, …).
   Setting `CRON_SECRET` makes Vercel Cron send it automatically as a Bearer token.
2. Repoint the Twilio WhatsApp webhook at `https://<your-app>.vercel.app/api/webhook`.
3. The daily cron (defined in `vercel.json`, default **13:00 UTC**) appears under
   **Project → Settings → Cron Jobs**. Adjust the schedule there or in `vercel.json`.

---

## Configuration reference

All configuration is via environment variables — see [`.env.example`](.env.example).
Notable ones:

- `COACH_MODEL` — Claude model for vision + coaching. Defaults to `claude-opus-4-8`
  (accuracy-leaning). Set to `claude-sonnet-5` for lower cost/latency.
- `DEFAULT_CALORIE_GOAL` — starting daily goal for new users (default `2000`).

---

## Project layout

```
api/
  webhook.py          # Twilio inbound webhook  (/api/webhook)
  nudge.py            # Vercel Cron target       (/api/nudge)
  _lib/
    config.py         # env-var settings
    db.py             # Postgres access (psycopg 3)
    twilio_client.py  # signature verify, media fetch, outbound send
    coach.py          # Claude vision / estimate / chat / nudge calls
    handlers.py       # inbound message routing
schema.sql            # database schema
scripts/smoke.py      # vision smoke test
index.html            # marketing/landing page (served at / by Vercel)
vercel.json           # function config + cron schedule
```

### Landing page

`index.html` is a self-contained marketing page explaining the coach, with
recommended pricing tiers and a monetization plan. Vercel serves it at `/`
alongside the `/api/*` functions. Update the "Open WhatsApp" button to your
`https://wa.me/<number>?text=join%20<sandbox-code>` link before going live.

---

## Notes & limitations (v1)

- Identity is the WhatsApp number; there's no separate login. `stop`/`start` is the opt-out.
- One image per message is analyzed (`MediaUrl0`); multi-image messages take the first.
- The inbound webhook processes the estimate synchronously so Twilio can render the reply.
  Vision + structured output with a small token budget stays within Twilio's ~15s window.
  If large photos ever time out, move the analysis to a queue (e.g. Upstash QStash) and
  send the reply asynchronously via the Twilio REST API — the `twilio_client.send` helper
  is already there for that.
- Calorie estimates are approximate and labeled as such in every reply.
