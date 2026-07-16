import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from config import BRAND_KEYWORDS

IST = timezone(timedelta(hours=5, minutes=30))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def _clean_html(raw: str) -> str:
    return BeautifulSoup(raw or "", "html.parser").get_text(separator=" ", strip=True)


def _parse_date(entry) -> datetime | None:
    for field in ("published", "updated"):
        val = entry.get(field, "")
        if not val:
            continue
        try:
            return parsedate_to_datetime(val).astimezone(timezone.utc)
        except Exception:
            pass
        try:
            return datetime.strptime(val, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return None


def _keyword_match(text: str) -> bool:
    t = text.lower()
    return any(kw.lower() in t for kw in BRAND_KEYWORDS)


def fetch_feed(url: str, label: str, filter_keywords: bool = True) -> list[dict]:
    today = datetime.now(IST).date()  # today's date in IST
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
    except Exception as e:
        print(f"  [{label}] Fetch error: {e}")
        return []

    mentions = []
    for entry in feed.entries:
        link = entry.get("link", "").strip()
        if not link:
            continue

        title = entry.get("title", "")
        summary_raw = entry.get("summary", "") or entry.get("description", "")
        content_raw = entry["content"][0].get("value", "") if entry.get("content") else ""
        full_text = _clean_html(content_raw or summary_raw)

        if filter_keywords and not _keyword_match(f"{title} {full_text}"):
            continue

        pub_date = _parse_date(entry)
        if not pub_date or pub_date.astimezone(IST).date() != today:
            continue

        author = (
            entry.get("author", "")
            or entry.get("dc_creator", "")
            or entry.get("source", {}).get("title", "")
        )

        mentions.append({
            "platform": label,
            "url": link,
            "title": title,
            "author": author,
            "post_date": pub_date.strftime("%Y-%m-%d %H:%M UTC") if pub_date else "",
            "content": full_text[:2000],
        })

    return mentions
