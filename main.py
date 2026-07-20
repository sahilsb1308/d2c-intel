from datetime import datetime
import ai_processor
import sheets_writer
from scrapers.rss_scraper import fetch_feed
from config import BRANDS


def run_brand(brand: dict):
    name = brand["name"]
    keywords = brand["keywords"]
    tab = brand["tab"]
    feeds = brand["feeds"]

    print(f"\n{'='*60}")
    print(f"{name} Monitor — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Writing to tab: '{tab}'")
    print("="*60)

    existing = sheets_writer.get_existing_links(tab)
    print(f"\n{len(existing)} posts already tracked in sheet")

    all_new = []
    for feed_cfg in feeds:
        label = feed_cfg["label"]
        raw = fetch_feed(feed_cfg["url"], label, keywords=keywords, filter_keywords=feed_cfg.get("filter_keywords", True))
        new = [m for m in raw if m["url"] not in existing]
        print(f"  [{label}] {len(raw)} fetched | {len(new)} new")
        all_new.extend(new)

    if not all_new:
        print("\nNothing new. Done.")
        return

    print(f"\nAI processing {len(all_new)} new posts...")
    processed = []
    for i, m in enumerate(all_new, 1):
        result = ai_processor.process(m, brand_name=name)
        processed.append(result)
        print(f"  [{i}/{len(all_new)}] [{result['category']}] {m['title'][:65]}")

    sheets_writer.append_mentions(tab, processed)
    print(f"\nDone — {len(processed)} new rows added to '{tab}'")


def run():
    for brand in BRANDS:
        run_brand(brand)


if __name__ == "__main__":
    run()
