import os
import requests
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))
YT_BASE = "https://www.googleapis.com/youtube/v3"


def fetch_youtube(keywords: list[str], exclude_keywords: list[str] | None = None) -> list[dict]:
    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        print("  [YouTube] No API key, skipping")
        return []

    today = datetime.now(IST).date()
    published_after = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=IST) \
        .astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    query = " OR ".join(f'"{kw}"' for kw in keywords[:3])

    try:
        search = requests.get(f"{YT_BASE}/search", params={
            "part": "snippet",
            "q": query,
            "type": "video",
            "publishedAfter": published_after,
            "order": "relevance",
            "maxResults": 15,
            "regionCode": "IN",
            "relevanceLanguage": "en",
            "key": api_key,
        }, timeout=15)
        search.raise_for_status()
        items = search.json().get("items", [])
    except Exception as e:
        print(f"  [YouTube] Search error: {e}")
        return []

    if not items:
        return []

    video_ids = [i["id"]["videoId"] for i in items]

    try:
        stats = requests.get(f"{YT_BASE}/videos", params={
            "part": "statistics,snippet",
            "id": ",".join(video_ids),
            "key": api_key,
        }, timeout=15)
        stats.raise_for_status()
        videos = stats.json().get("items", [])
    except Exception as e:
        print(f"  [YouTube] Stats error: {e}")
        return []

    mentions = []
    for v in videos:
        snippet = v.get("snippet", {})
        vstats = v.get("statistics", {})

        title = snippet.get("title", "")
        description = snippet.get("description", "")[:600]
        channel = snippet.get("channelTitle", "")
        url = f"https://www.youtube.com/watch?v={v['id']}"
        pub_date = snippet.get("publishedAt", "")

        views = int(vstats.get("viewCount", 0))
        likes = int(vstats.get("likeCount", 0))
        comments = int(vstats.get("commentCount", 0))

        combined = f"{title} {description}".lower()

        if not any(kw.lower() in combined for kw in keywords):
            continue

        if exclude_keywords and any(kw in combined for kw in exclude_keywords):
            print(f"  [YouTube] Excluded (off-topic): {title[:60]}")
            continue

        try:
            pub_dt = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
            if pub_dt.astimezone(IST).date() != today:
                continue
        except Exception:
            continue

        mentions.append({
            "platform": "YouTube",
            "url": url,
            "title": title,
            "author": channel,
            "post_date": pub_date,
            "content": (
                f"{description}\n\n"
                f"Views: {views:,} | Likes: {likes:,} | Comments: {comments:,}"
            ),
            "views": views,
            "likes": likes,
            "comments": comments,
        })

    return mentions
