import datetime
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from config import GOOGLE_TOKEN_DATA

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def get_credentials():
    if not GOOGLE_TOKEN_DATA:
        raise RuntimeError("GOOGLE_TOKEN_JSON env var is missing!")

    creds = Credentials(
        token=GOOGLE_TOKEN_DATA["token"],
        refresh_token=GOOGLE_TOKEN_DATA["refresh_token"],
        token_uri=GOOGLE_TOKEN_DATA["token_uri"],
        client_id=GOOGLE_TOKEN_DATA["client_id"],
        client_secret=GOOGLE_TOKEN_DATA["client_secret"],
        scopes=GOOGLE_TOKEN_DATA["scopes"],
    )

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            print("[calendar_utils] Token refreshed ✅")
        except Exception as e:
            print(f"[calendar_utils] Refresh failed: {e}")
            raise

    return creds


def create_google_meet(meeting: dict) -> str:
    creds   = get_credentials()
    service = build("calendar", "v3", credentials=creds)

    start_time = datetime.datetime.fromisoformat(
        f"{meeting['meeting_date']}T{meeting['meeting_time']}:00"
    )
    end_time = start_time + datetime.timedelta(
        minutes=int(meeting["duration_minutes"])
    )

    event = {
        "summary":     meeting.get("agenda", "Meeting"),
        "description": "Scheduled via EquitySoft AI Meeting Scheduler Bot 🤖",
        "start": {"dateTime": start_time.isoformat(), "timeZone": "Asia/Kolkata"},
        "end":   {"dateTime": end_time.isoformat(),   "timeZone": "Asia/Kolkata"},
        "conferenceData": {
            "createRequest": {"requestId": f"meet-{int(start_time.timestamp())}"}
        },
        "attendees": [],
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email",  "minutes": 60},
                {"method": "popup",  "minutes": 10},
            ],
        },
    }

    if meeting.get("participant_email"):
        event["attendees"].append({"email": meeting["participant_email"]})

    created_event = service.events().insert(
        calendarId="primary",
        body=event,
        conferenceDataVersion=1,
        sendUpdates="all",
    ).execute()

    return created_event["hangoutLink"]