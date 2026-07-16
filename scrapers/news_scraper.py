"""
Scrapes Google News RSS for news articles mentioning Swiss Beauty.
Also searches for LinkedIn posts via Google search (site:linkedin.com).
"""
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from config import BRAND_KEYWORDS, LOOKBACK_HOURS

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def _parse_date(date_str: str) -> datetime | None:
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            pass
    return None


def _scrape_google_news(keyword: str, cutoff: datetime) -> list[dict]:
    url = f"https://news.google.com/rss/search?q={requests.utils.quote(keyword)}&hl=en-IN&gl=IN&ceid=IN:en"
    try:
        feed = feedparser.parse(url)
    except Exception as e:
        print(f"  [news] feedparser error for '{keyword}': {e}")
        return []

    mentions = []
    for entry in feed.entries:
        pub_date = _parse_date(entry.get("published", ""))
        if pub_date and pub_date < cutoff:
            continue
        mentions.append({
            "platform": "News Article",
            "url": entry.get("link", ""),
            "author": entry.get("source", {}).get("title", "Unknown Source"),
            "post_date": pub_date.strftime("%Y-%m-%d %H:%M UTC") if pub_date else "",
            "content": BeautifulSoup(entry.get("summary", ""), "html.parser").get_text()[:500],
            "engagement": "",
        })
    return mentions


def _scrape_linkedin_via_google(keyword: str) -> list[dict]:
    """Uses Google search to find public LinkedIn posts mentioning the keyword."""
    query = f'site:linkedin.com "{keyword}"'
    url = f"https://www.google.com/search?q={requests.utils.quote(query)}&num=20"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        mentions = []
        for a in soup.select("a[href]"):
            href = a["href"]
            if "linkedin.com" in href and "/posts/" in href:
                title = a.get_text(strip=True)
                if keyword.lower() in title.lower() or not title:
                    mentions.append({
                        "platform": "LinkedIn",
                        "url": href.split("&")[0],
                        "author": "",
                        "post_date": "",
                        "content": title,
                        "engagement": "",
                    })
        return mentions
    except Exception as e:
        print(f"  [linkedin] Google scrape error for '{keyword}': {e}")
        return []


def scrape() -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    all_mentions = []
    seen_urls = set()

    for keyword in BRAND_KEYWORDS:
        for m in _scrape_google_news(keyword, cutoff):
            if m["url"] not in seen_urls:
                seen_urls.add(m["url"])
                all_mentions.append(m)

        for m in _scrape_linkedin_via_google(keyword):
            if m["url"] not in seen_urls:
                seen_urls.add(m["url"])
                all_mentions.append(m)

    news_count = sum(1 for m in all_mentions if m["platform"] == "News Article")
    li_count = sum(1 for m in all_mentions if m["platform"] == "LinkedIn")
    print(f"  [news] Found {news_count} articles, {li_count} LinkedIn posts")
    return all_mentions
