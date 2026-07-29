from datetime import datetime
import os
import requests as http_requests
import ai_processor
import sheets_writer
from scrapers.rss_scraper import fetch_feed
from config import BRANDS


def run_brand(brand: dict) -> list[dict]:
    name = brand["name"]
    keywords = brand["keywords"]
    tab = brand["tab"]
    feeds = brand["feeds"]

    print(f"\n{'='*60}")
    print(f"{name} Monitor — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Writing to tab: '{tab}'")
    print("="*60)

    exclude_keywords = brand.get("exclude_keywords", [])
    all_new = []
    for feed_cfg in feeds:
        label = feed_cfg["label"]
        raw = fetch_feed(feed_cfg["url"], label, keywords=keywords,
                         filter_keywords=feed_cfg.get("filter_keywords", True),
                         exclude_keywords=exclude_keywords)
        print(f"  [{label}] {len(raw)} fetched")
        all_new.extend(raw)

    if not all_new:
        print("\nNothing new. Done.")
        return []

    print(f"\nAI processing {len(all_new)} new posts...")
    processed = []
    for i, m in enumerate(all_new, 1):
        result = ai_processor.process(m, brand_name=name)

        # Post-AI exclude check: drop if summary reveals off-topic content
        summary_lower = result.get("summary", "").lower()
        title_lower = result.get("title", "").lower()
        combined = f"{title_lower} {summary_lower}"
        if exclude_keywords and any(kw in combined for kw in exclude_keywords):
            print(f"  [{i}/{len(all_new)}] Dropped after AI (off-topic): {m['title'][:65]}")
            continue

        # Drop General Mention posts where the brand name doesn't appear in the summary
        # — catches noisy X/Reddit posts that matched keywords but aren't about the brand
        if result.get("category") == "General Mention":
            brand_mentioned = any(kw.lower() in combined for kw in keywords)
            if not brand_mentioned:
                print(f"  [{i}/{len(all_new)}] Dropped (off-brand General Mention): {m['title'][:65]}")
                continue

        processed.append(result)
        print(f"  [{i}/{len(all_new)}] [{result['category']}] {m['title'][:65]}")

    sheets_writer.append_mentions(tab, processed)
    print(f"\nDone — {len(processed)} new rows added to '{tab}'")

    # Return posts for webhook with brand name attached
    return [{"brand": name, **p} for p in processed]


def fire_webhook(all_posts: list[dict]):
    webhook_url = os.getenv("N8N_WEBHOOK_URL", "").strip()
    if not webhook_url or not all_posts:
        return

    payload = {"posts": [{
        "brand":     p.get("brand", ""),
        "category":  p.get("category", "General Mention"),
        "sentiment": p.get("sentiment", "neutral").capitalize(),
        "platform":  p.get("platform", ""),
        "title":     p.get("title", "")[:200],
        "url":       p.get("url", ""),
    } for p in all_posts]}

    try:
        resp = http_requests.post(webhook_url, json=payload, timeout=15)
        print(f"\n[webhook] Fired — {len(all_posts)} posts sent ({resp.status_code})")
    except Exception as e:
        print(f"\n[webhook] Failed: {e}")


def run():
    all_new_posts = []
    for brand in BRANDS:
        posts = run_brand(brand)
        all_new_posts.extend(posts)

    fire_webhook(all_new_posts)


if __name__ == "__main__":
    run()
