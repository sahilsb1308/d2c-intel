"""
Twitter scraper using twscrape (unofficial, no paid API needed).
First run: you need to add a Twitter account via CLI:
  twscrape add_accounts accounts.txt  (format: username:password:email:email_password)
  twscrape login_all
"""
import asyncio
from datetime import datetime, timezone, timedelta
from config import BRAND_KEYWORDS, LOOKBACK_HOURS


async def _search_twitter(keywords: list[str], cutoff: datetime) -> list[dict]:
    try:
        from twscrape import API
    except ImportError:
        return []

    api = API()
    mentions = []
    seen_ids = set()

    for keyword in keywords:
        query = f'"{keyword}" lang:en -is:retweet'
        try:
            async for tweet in api.search(query, limit=100):
                if tweet.date < cutoff:
                    continue
                if tweet.id in seen_ids:
                    continue
                seen_ids.add(tweet.id)
                mentions.append({
                    "platform": "Twitter/X",
                    "url": f"https://twitter.com/{tweet.user.username}/status/{tweet.id}",
                    "author": f"@{tweet.user.username}",
                    "post_date": tweet.date.strftime("%Y-%m-%d %H:%M UTC"),
                    "content": tweet.rawContent,
                    "engagement": f"❤️{tweet.likeCount} | 🔁{tweet.retweetCount} | 💬{tweet.replyCount}",
                })
        except Exception as e:
            print(f"  [twitter] Error searching '{keyword}': {e}")

    return mentions


def scrape() -> list[dict]:
    try:
        import twscrape  # noqa: F401
    except ImportError:
        print("  [twitter] twscrape not installed — run: pip install twscrape")
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    try:
        mentions = asyncio.run(_search_twitter(BRAND_KEYWORDS, cutoff))
    except RuntimeError:
        # Already inside an event loop (e.g. Jupyter)
        loop = asyncio.new_event_loop()
        mentions = loop.run_until_complete(_search_twitter(BRAND_KEYWORDS, cutoff))
        loop.close()

    print(f"  [twitter] Found {len(mentions)} mentions")
    return mentions
