import re
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

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
    # Only use `published` — never `updated`, which Google News stamps with today
    # when resurfacing old articles, causing stale content to pass the date filter
    val = entry.get("published", "")
    if not val:
        return None
    try:
        return parsedate_to_datetime(val).astimezone(timezone.utc)
    except Exception:
        pass
    try:
        return datetime.strptime(val, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        pass
    return None


_MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
}


def _parse_text_date(text: str) -> datetime | None:
    """Parse human-readable dates like 'Jun 11, 2026' or '11 June 2026' from page text."""
    # "Jun 11, 2026" or "June 11, 2026"
    m = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),?\s+(20\d{2})', text, re.IGNORECASE)
    if m:
        try:
            month = _MONTH_MAP[m.group(1)[:3].lower()]
            return datetime(int(m.group(3)), month, int(m.group(2)), tzinfo=timezone.utc)
        except Exception:
            pass
    # "11 Jun 2026" or "11 June 2026"
    m = re.search(r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(20\d{2})', text, re.IGNORECASE)
    if m:
        try:
            month = _MONTH_MAP[m.group(2)[:3].lower()]
            return datetime(int(m.group(3)), month, int(m.group(1)), tzinfo=timezone.utc)
        except Exception:
            pass
    return None


def _fetch_article_date(url: str) -> datetime | None:
    """Fetch the article page and extract its actual published date from meta tags.
    Used to catch RSS feeds that stamp old articles with today's date."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)

        # Search raw HTML for ISO date strings (catches JS-rendered sites where
        # the date is in a data attribute or script tag, e.g. "2026-02-02")
        iso_dates = re.findall(r'(20\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])', resp.text[:60000])
        if iso_dates:
            try:
                y, mo, d = iso_dates[0]
                return datetime(int(y), int(mo), int(d), tzinfo=timezone.utc)
            except Exception:
                pass

        soup = BeautifulSoup(resp.text, "html.parser")

        # Standard article publish date meta tags
        candidates = [
            ("meta", {"property": "article:published_time"}),
            ("meta", {"name": "publish-date"}),
            ("meta", {"name": "date"}),
            ("meta", {"name": "pubdate"}),
            ("meta", {"property": "og:pubdate"}),
            ("meta", {"itemprop": "datePublished"}),
        ]
        for tag_name, attrs in candidates:
            tag = soup.find(tag_name, attrs)
            if tag and tag.get("content"):
                raw = tag["content"]
                try:
                    return parsedate_to_datetime(raw).astimezone(timezone.utc)
                except Exception:
                    pass
                try:
                    return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
                except Exception:
                    pass

        # Try <time datetime="...">
        time_tag = soup.find("time", {"datetime": True})
        if time_tag:
            raw = time_tag["datetime"]
            try:
                return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
            except Exception:
                pass

        # Try elements with date-related class/id names, skip live-clock elements
        for date_el in soup.find_all(class_=re.compile(r'date|publish|byline|posted|timestamp', re.I)):
            classes = ' '.join(date_el.get('class', []))
            if re.search(r'today|current|now|live', classes, re.I):
                continue
            parsed = _parse_text_date(date_el.get_text())
            if parsed:
                return parsed

        # Normalize page text to single line (avoids newline breaks mid-date)
        full_text = soup.get_text(separator=' ', strip=True)

        # Look for "Published" keyword context — catches sites like indiaretailing.com
        # that show "Published On : Mon, 2 Feb 2026 , 12 : 35 pm"
        pub_match = re.search(r'[Pp]ublish(?:ed)?\s*[Oo]n?\s*[:\-]?\s*(.{5,80})', full_text)
        if pub_match:
            parsed = _parse_text_date(pub_match.group(1))
            if parsed:
                return parsed

        # Last resort: scan page text but skip first 500 chars (nav/header with live
        # clock) to avoid picking up the site's current-date display
        parsed = _parse_text_date(full_text[500:5000])
        if parsed:
            return parsed

    except Exception:
        pass

    # Fallback: extract date from URL path e.g. /2026/01/20/
    m = re.search(r'/(\d{4})[/-](\d{2})[/-](\d{2})/', url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                            tzinfo=timezone.utc)
        except Exception:
            pass

    return None


def _keyword_match(text: str, keywords: list[str]) -> bool:
    t = text.lower()
    return any(kw.lower() in t for kw in keywords)


def _exclude_match(text: str, exclude_keywords: list[str]) -> bool:
    t = text.lower()
    return any(kw in t for kw in exclude_keywords)


def fetch_feed(url: str, label: str, keywords: list[str], filter_keywords: bool = True, exclude_keywords: list[str] | None = None) -> list[dict]:
    today = datetime.now(IST).date()
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

        if filter_keywords and not _keyword_match(f"{title} {full_text}", keywords):
            continue

        if exclude_keywords and _exclude_match(f"{title} {full_text}", exclude_keywords):
            print(f"  [{label}] Excluded (off-topic): {title[:60]}")
            continue

        # First pass: check RSS published date
        pub_date = _parse_date(entry)
        if not pub_date or pub_date.astimezone(IST).date() != today:
            continue

        # Second pass: verify against the article's actual published date
        # (RSS feeds like Google News re-index old articles with today's date)
        actual_date = _fetch_article_date(link)
        if actual_date and actual_date.astimezone(IST).date() != today:
            print(f"  [{label}] Skipped old article re-indexed today: {title[:60]}")
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
