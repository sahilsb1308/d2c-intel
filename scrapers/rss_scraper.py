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


def _fetch_article_date(url: str) -> datetime | None:
    """Fetch the article page and extract its actual published date from meta tags.
    Used to catch RSS feeds that stamp old articles with today's date."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
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

    except Exception:
        pass
    return None


def _keyword_match(text: str, keywords: list[str]) -> bool:
    t = text.lower()
    return any(kw.lower() in t for kw in keywords)


def fetch_feed(url: str, label: str, keywords: list[str], filter_keywords: bool = True) -> list[dict]:
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
