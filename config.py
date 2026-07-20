import os
import json
import tempfile
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

# Support both a file path (local) and raw JSON content (GitHub Actions secret)
_json_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
_json_content = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT", "")

if _json_content:
    _tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w")
    _tmp.write(_json_content)
    _tmp.close()
    GOOGLE_SERVICE_ACCOUNT_JSON = _tmp.name
else:
    GOOGLE_SERVICE_ACCOUNT_JSON = _json_path

# Legacy single-brand vars (kept for backward compat)
BRAND_NAME = os.getenv("BRAND_NAME", "Swiss Beauty")
BRAND_KEYWORDS = [k.strip() for k in os.getenv("BRAND_KEYWORDS", "Swiss Beauty").split(",")]
SHEET_TAB_NAME = os.getenv("SHEET_TAB_NAME", "Swiss Beauty")


def _load_rss_feeds_for_prefix(prefix: str) -> list[dict]:
    base = f"{prefix}RSS_FEEDS"
    feeds = []
    for key in sorted(k for k in os.environ if k == base or k.startswith(base + "_")):
        val = os.getenv(key, "").strip()
        parts = val.split("|")
        if len(parts) >= 2:
            feeds.append({
                "label": parts[0].strip(),
                "url": parts[1].strip(),
                "filter_keywords": (parts[2].strip().lower() != "no") if len(parts) > 2 else True,
            })
    return feeds


def _load_exclude_keywords(prefix: str) -> list[str]:
    val = os.getenv(f"{prefix}EXCLUDE_KEYWORDS", "").strip()
    return [k.strip().lower() for k in val.split(",") if k.strip()]


def _load_brands() -> list[dict]:
    brands = []

    # Brand 1: Swiss Beauty (existing env vars)
    feeds = _load_rss_feeds_for_prefix("")
    if BRAND_NAME:
        brands.append({
            "name": BRAND_NAME,
            "keywords": BRAND_KEYWORDS,
            "exclude_keywords": _load_exclude_keywords(""),
            "tab": SHEET_TAB_NAME,
            "feeds": feeds,
        })

    # Additional brands: BRAND_2_*, BRAND_3_*, ...
    for n in range(2, 20):
        name = os.getenv(f"BRAND_{n}_NAME", "").strip()
        if not name:
            break
        keywords = [k.strip() for k in os.getenv(f"BRAND_{n}_KEYWORDS", name).split(",")]
        tab = os.getenv(f"BRAND_{n}_TAB", name)
        feeds = _load_rss_feeds_for_prefix(f"BRAND_{n}_")
        brands.append({
            "name": name,
            "keywords": keywords,
            "exclude_keywords": _load_exclude_keywords(f"BRAND_{n}_"),
            "tab": tab,
            "feeds": feeds,
        })

    return brands


BRANDS = _load_brands()
RSS_FEEDS = BRANDS[0]["feeds"] if BRANDS else []
