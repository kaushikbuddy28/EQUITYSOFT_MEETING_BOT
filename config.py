import os
import json
from dotenv import load_dotenv
load_dotenv()

# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL        = os.getenv("WEBHOOK_URL")

# ── Gemini ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ── Google Token (stored as JSON string in env var) ───────────────────────────
_raw = os.getenv("GOOGLE_TOKEN_JSON")
GOOGLE_TOKEN_DATA = json.loads(_raw) if _raw else {}