import os
import json
import tempfile
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SHEET_TAB_NAME = os.getenv("SHEET_TAB_NAME", "Swiss Beauty")

BRAND_NAME = os.getenv("BRAND_NAME", "Swiss Beauty")
BRAND_KEYWORDS = [k.strip() for k in os.getenv("BRAND_KEYWORDS", "Swiss Beauty").split(",")]

# Support both a file path (local) and raw JSON content (GitHub Actions secret)
_json_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
_json_content = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT", "")

if _json_content:
    # Write JSON content to a temp file for gspread
    _tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w")
    _tmp.write(_json_content)
    _tmp.close()
    GOOGLE_SERVICE_ACCOUNT_JSON = _tmp.name
else:
    GOOGLE_SERVICE_ACCOUNT_JSON = _json_path


def _load_rss_feeds() -> list[dict]:
    feeds = []
    for key in sorted(k for k in os.environ if k == "RSS_FEEDS" or k.startswith("RSS_FEEDS_")):
        val = os.getenv(key, "").strip()
        parts = val.split("|")
        if len(parts) >= 2:
            feeds.append({
                "label": parts[0].strip(),
                "url": parts[1].strip(),
                "filter_keywords": (parts[2].strip().lower() != "no") if len(parts) > 2 else True,
            })
    return feeds

RSS_FEEDS = _load_rss_feeds()
