import google.generativeai as genai
import json
import re
from config import GEMINI_API_KEY
from prompts import MEETING_EXTRACTION_PROMPT

genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel("gemini-2.5-flash")


def extract_json_from_text(text: str):
    """Extract JSON from Gemini response even if wrapped in markdown."""
    text = re.sub(r"```json|```", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON found in Gemini response")
    return json.loads(match.group())


def extract_meeting_details(user_input: str) -> dict:
    """
    Send user input to Gemini and extract structured meeting details.
    Returns a dict — missing fields will simply be absent or None.
    """
    prompt = MEETING_EXTRACTION_PROMPT.format(user_input=user_input)

    try:
        response = model.generate_content(prompt)
        return extract_json_from_text(response.text)
    except Exception as e:
        print(f"[gemini_utils] Error: {e}")
        return {}   # Return empty dict — caller handles missing fields
