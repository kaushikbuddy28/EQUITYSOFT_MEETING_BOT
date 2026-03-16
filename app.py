from flask import Flask, request, jsonify
from flask_cors import CORS
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
import requests
import time
import os

from config import TELEGRAM_BOT_TOKEN, WEBHOOK_URL
from gemini_utils import extract_meeting_details
from calendar_utils import create_google_meet

app = Flask(__name__)
CORS(app)

# ─── Telegram ─────────────────────────────────────────────────────────────────
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# ─── Concurrency ──────────────────────────────────────────────────────────────
executor = ThreadPoolExecutor(max_workers=20)

# ─── Dedup ────────────────────────────────────────────────────────────────────
processed_updates = set()
MAX_PROCESSED_IDS = 1000

# ─── Session state per user ───────────────────────────────────────────────────
# Stores partially collected meeting details while conversation is ongoing
user_sessions   = defaultdict(dict)   # chat_id → {meeting_date, meeting_time, ...}
last_activity   = {}
SESSION_TIMEOUT = 1800                 # 30 min idle clears session

FIELD_LABELS = {
    "participant_name":  "participant's name",
    "participant_email": "participant's email address",
    "meeting_date":      "meeting date (e.g. 2025-07-20)",
    "meeting_time":      "meeting time in 24-hr format (e.g. 14:30)",
    "duration_minutes":  "meeting duration in minutes (e.g. 30)",
    "agenda":            "meeting agenda or topic",
}

REQUIRED_FIELDS = [
    "meeting_date",
    "meeting_time",
    "duration_minutes",
    "participant_email",
]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def send_message(chat_id, text):
    try:
        requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception as e:
        print(f"[send_message] {e}")


def send_typing(chat_id):
    try:
        requests.post(
            f"{TELEGRAM_API}/sendChatAction",
            json={"chat_id": chat_id, "action": "typing"},
            timeout=5,
        )
    except Exception:
        pass


def clean_old_sessions():
    now = time.time()
    expired = [uid for uid, t in last_activity.items() if now - t > SESSION_TIMEOUT]
    for uid in expired:
        user_sessions.pop(uid, None)
        last_activity.pop(uid, None)


def merge_extracted(existing: dict, new: dict) -> dict:
    """Merge newly extracted fields into the existing session (skip None/empty)."""
    for key, value in new.items():
        if value and key != "missing_fields" and key != "error":
            existing[key] = value
    return existing


def get_missing(session: dict) -> list:
    return [f for f in REQUIRED_FIELDS if not session.get(f)]


# ─── Core processor (runs in background thread) ───────────────────────────────

def process_message(chat_id, first_name, user_text):
    send_typing(chat_id)
    clean_old_sessions()
    last_activity[chat_id] = time.time()

    session = user_sessions[chat_id]

    # ── Try to extract meeting details from the user message ──
    try:
        extracted = extract_meeting_details(user_text)
    except Exception as e:
        print(f"[process_message] Gemini error: {e}")
        send_message(chat_id,
            "⚠️ I had trouble understanding that. Could you rephrase?\n\n"
            "Example: _Schedule a 30-min call with john@example.com on July 20 at 3pm to discuss the project._"
        )
        return

    # Merge into session (accumulate across turns)
    merge_extracted(session, extracted)
    missing = get_missing(session)

    # ── Still missing required fields → ask for them ──
    if missing:
        next_field = missing[0]
        label = FIELD_LABELS.get(next_field, next_field)

        # First time or new session
        if not any(session.values()):
            send_message(chat_id,
                f"📅 I'd love to schedule a meeting for you, {first_name}!\n\n"
                f"Let's start — what is the *{label}*?"
            )
        else:
            collected = len(REQUIRED_FIELDS) - len(missing)
            send_message(chat_id,
                f"Got it! ✅ ({collected}/{len(REQUIRED_FIELDS)} details collected)\n\n"
                f"Now please share the *{label}*:"
            )
        return

    # ── All required fields present → schedule meeting ──
    send_typing(chat_id)
    send_message(chat_id, "⏳ All details collected! Scheduling your Google Meet now...")

    try:
        meet_link = create_google_meet(session)
    except Exception as e:
        print(f"[process_message] Calendar error: {e}")
        send_message(chat_id,
            "❌ Failed to create the meeting. Please check the details and try again.\n\n"
            "You can also contact us at 📧 business@equitysoft.in"
        )
        # Clear session so user can retry
        user_sessions.pop(chat_id, None)
        return

    # Build confirmation message
    agenda        = session.get("agenda", "Meeting")
    date          = session.get("meeting_date", "")
    time_val      = session.get("meeting_time", "")
    duration      = session.get("duration_minutes", "")
    p_name        = session.get("participant_name", "")
    p_email       = session.get("participant_email", "")

    reply = (
        f"✅ *Meeting Scheduled Successfully!*\n\n"
        f"📌 *Agenda:* {agenda}\n"
        f"📅 *Date:* {date}\n"
        f"🕐 *Time:* {time_val} IST\n"
        f"⏱ *Duration:* {duration} minutes\n"
        f"👤 *Participant:* {p_name or p_email}\n"
        f"📧 *Invite sent to:* {p_email}\n\n"
        f"🔗 *Google Meet Link:*\n{meet_link}\n\n"
        f"_Calendar invite has been sent via email. Have a great meeting! 🚀_"
    )
    send_message(chat_id, reply)

    # Clear session after successful booking
    user_sessions.pop(chat_id, None)


# ─── Webhook ──────────────────────────────────────────────────────────────────

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json(silent=True)
    if not update:
        return jsonify({"status": "bad request"}), 400

    # Deduplicate Telegram retries
    update_id = update.get("update_id")
    if update_id in processed_updates:
        return jsonify({"status": "duplicate"}), 200
    processed_updates.add(update_id)
    if len(processed_updates) > MAX_PROCESSED_IDS:
        processed_updates.clear()

    if "message" not in update:
        return jsonify({"status": "no message"}), 200

    message    = update["message"]
    chat_id    = message["chat"]["id"]
    first_name = message.get("from", {}).get("first_name", "there")
    user_text  = message.get("text", "").strip()

    if not user_text:
        return jsonify({"status": "empty"}), 200

    # ── /start ──
    if user_text == "/start":
        send_message(chat_id,
            f"👋 Hello *{first_name}*! I'm your AI Meeting Scheduler 🤖\n\n"
            "I can schedule a *Google Meet* for you in seconds!\n\n"
            "Just tell me something like:\n"
            "💬 _Schedule a 30-min meeting with john@example.com on July 20 at 3pm to discuss the project_\n\n"
            "Or simply describe your meeting and I'll ask for any missing details.\n\n"
            "Commands:\n"
            "/schedule — Start scheduling a new meeting\n"
            "/cancel   — Cancel ongoing booking\n"
            "/help     — How to use this bot"
        )
        return jsonify({"status": "ok"}), 200

    # ── /cancel ──
    if user_text == "/cancel":
        user_sessions.pop(chat_id, None)
        send_message(chat_id,
            "🚫 Booking cancelled.\n\nSend a new message whenever you're ready to schedule a meeting!"
        )
        return jsonify({"status": "ok"}), 200

    # ── /schedule ──
    if user_text == "/schedule":
        user_sessions.pop(chat_id, None)   # fresh session
        send_message(chat_id,
            "📅 Let's schedule a meeting!\n\n"
            "Please tell me:\n"
            "• *Who* are you meeting? (name & email)\n"
            "• *When?* (date & time)\n"
            "• *How long?* (duration in minutes)\n"
            "• *What's it about?* (agenda)\n\n"
            "You can tell me everything at once or one by one 😊"
        )
        return jsonify({"status": "ok"}), 200

    # ── /help ──
    if user_text == "/help":
        send_message(chat_id,
            "🆘 *How to use this bot:*\n\n"
            "Simply describe your meeting in natural language:\n\n"
            "✅ _Meet with priya@company.com on 25 July at 2pm for 45 minutes to review the proposal_\n\n"
            "I'll extract all the details and create the Google Meet automatically.\n\n"
            "If anything is missing, I'll ask you step by step.\n\n"
            "*Commands:*\n"
            "/schedule — Fresh booking\n"
            "/cancel   — Cancel current booking\n"
            "/start    — Welcome message\n"
            "/help     — This message"
        )
        return jsonify({"status": "ok"}), 200

    # ── All other messages → AI processing in background ──
    executor.submit(process_message, chat_id, first_name, user_text)
    return jsonify({"status": "processing"}), 200


# ─── Health check ─────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "running ✅",
        "bot": "EquitySoft AI Meeting Scheduler",
        "active_sessions": len(user_sessions),
    }), 200


# ─── Set / Remove webhook ─────────────────────────────────────────────────────

@app.route("/set-webhook", methods=["GET"])
def set_webhook():
    url = f"{TELEGRAM_API}/setWebhook?url={WEBHOOK_URL}"
    res = requests.get(url, timeout=10)
    return jsonify(res.json())


@app.route("/remove-webhook", methods=["GET"])
def remove_webhook():
    url = f"{TELEGRAM_API}/setWebhook?url="
    res = requests.get(url, timeout=10)
    return jsonify(res.json())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7000, debug=False, threaded=True)
