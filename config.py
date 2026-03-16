import os
from dotenv import load_dotenv

load_dotenv()

# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8710669911:AAF_XWMrhoo4rU5vLRCuCx_bD0pwsWo4DoY")
WEBHOOK_URL        = os.getenv("WEBHOOK_URL", "https://YOUR_DOMAIN/webhook")

# ── Gemini ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyDCnjx4U3TOG2VN9mzdP6dZ45SmZl4txbY")

# ── Google Calendar ───────────────────────────────────────────────────────────
GOOGLE_CREDENTIALS_FILE = "credentials.json"
GOOGLE_TOKEN_FILE       = "token.json"

# ── Email (optional) ──────────────────────────────────────────────────────────
EMAIL_SENDER       = os.getenv("EMAIL_SENDER", "rahul.gajjar@equitysoft.in")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD", "Rahulgajjar@12")
