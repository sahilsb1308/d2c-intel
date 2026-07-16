"""
Swiss Beauty Brand Monitor
Fetches all RSS feeds and appends AI-processed mentions to the Swiss Beauty Google Sheet tab.

Usage:
    python main.py
"""
from datetime import datetime
import ai_processor
import sheets_writer
from scrapers.rss_scraper import fetch_feed
from config import RSS_FEEDS, BRAND_NAME, SHEET_TAB_NAME


def run():
    print(f"\n{'='*60}")
    print(f"{BRAND_NAME} Monitor — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Writing to tab: '{SHEET_TAB_NAME}'")
    print("="*60)

    # Load all URLs already in the sheet (dedup across all sources)
    existing = sheets_writer.get_existing_links(SHEET_TAB_NAME)
    print(f"\n{len(existing)} posts already tracked in sheet")

    # Fetch all RSS feeds
    all_new = []
    for feed_cfg in RSS_FEEDS:
        label = feed_cfg["label"]
        raw = fetch_feed(feed_cfg["url"], label, filter_keywords=feed_cfg.get("filter_keywords", True))
        new = [m for m in raw if m["url"] not in existing]
        print(f"  [{label}] {len(raw)} fetched | {len(new)} new")
        all_new.extend(new)

    if not all_new:
        print("\nNothing new. Done.")
        return

    # AI: generate summary + category
    print(f"\nAI processing {len(all_new)} new posts...")
    processed = []
    for i, m in enumerate(all_new, 1):
        result = ai_processor.process(m)
        processed.append(result)
        print(f"  [{i}/{len(all_new)}] [{result['category']}] {m['title'][:65]}")

    # Write all to Swiss Beauty tab
    sheets_writer.append_mentions(SHEET_TAB_NAME, processed)

    print(f"\nDone — {len(processed)} new rows added to '{SHEET_TAB_NAME}'")


if __name__ == "__main__":
    run()
