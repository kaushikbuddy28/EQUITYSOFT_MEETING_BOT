import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from config import GOOGLE_CREDENTIALS_FILE, GOOGLE_TOKEN_FILE

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def get_credentials():
    creds = None

    # Load existing token
    try:
        creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_FILE, SCOPES)
    except Exception:
        pass

    # Refresh if expired
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(GOOGLE_TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
            return creds
        except Exception as e:
            print(f"[calendar_utils] Token refresh failed: {e}")
            creds = None

    # If still no valid creds, run OAuth flow (only works locally)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            GOOGLE_CREDENTIALS_FILE, SCOPES
        )
        creds = flow.run_local_server(port=0)
        with open(GOOGLE_TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return creds


def create_google_meet(meeting: dict) -> str:
    """
    Creates a Google Calendar event with a Meet link.
    Sends email invite to participant_email.
    Returns the Google Meet link.
    """
    creds   = get_credentials()
    service = build("calendar", "v3", credentials=creds)

    start_time = datetime.datetime.fromisoformat(
        f"{meeting['meeting_date']}T{meeting['meeting_time']}:00"
    )
    end_time = start_time + datetime.timedelta(minutes=int(meeting["duration_minutes"]))

    event = {
        "summary":     meeting.get("agenda", "Meeting"),
        "description": "Scheduled via EquitySoft AI Meeting Scheduler Bot 🤖",
        "start": {
            "dateTime": start_time.isoformat(),
            "timeZone": "Asia/Kolkata",
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": "Asia/Kolkata",
        },
        "conferenceData": {
            "createRequest": {
                "requestId": f"meet-{int(start_time.timestamp())}"
            }
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

    # Add participant
    if meeting.get("participant_email"):
        event["attendees"].append({"email": meeting["participant_email"]})

    created_event = service.events().insert(
        calendarId="primary",
        body=event,
        conferenceDataVersion=1,
        sendUpdates="all",      # sends email invite automatically
    ).execute()

    return created_event["hangoutLink"]
