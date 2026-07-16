import praw
from datetime import datetime, timezone, timedelta
from config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT, BRAND_KEYWORDS, LOOKBACK_HOURS

TARGET_SUBREDDITS = [
    "all",  # search everything; praw limits to top results
    "beauty",
    "IndianBeautyDeals",
    "IndianMakeupAndBeauty",
    "MakeupAddiction",
    "SkincareAddiction",
    "india",
]


def scrape() -> list[dict]:
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        print("  [reddit] Skipped — REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET not set in .env")
        return []

    reddit = praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
    )

    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    mentions = []
    seen_urls = set()

    for keyword in BRAND_KEYWORDS:
        for subreddit_name in TARGET_SUBREDDITS:
            try:
                subreddit = reddit.subreddit(subreddit_name)
                for submission in subreddit.search(keyword, sort="new", time_filter="day", limit=50):
                    post_time = datetime.fromtimestamp(submission.created_utc, tz=timezone.utc)
                    if post_time < cutoff:
                        continue
                    url = f"https://reddit.com{submission.permalink}"
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    mentions.append({
                        "platform": "Reddit",
                        "url": url,
                        "author": str(submission.author) if submission.author else "[deleted]",
                        "post_date": post_time.strftime("%Y-%m-%d %H:%M UTC"),
                        "content": submission.title + ("\n" + submission.selftext if submission.selftext else ""),
                        "engagement": f"↑{submission.score} | 💬{submission.num_comments}",
                    })
            except Exception as e:
                print(f"  [reddit] Error scraping r/{subreddit_name} for '{keyword}': {e}")

    print(f"  [reddit] Found {len(mentions)} mentions")
    return mentions
