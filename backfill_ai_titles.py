"""
Backfill AI Title for existing rows that have an empty AI Title column.
Run once: python backfill_ai_titles.py
"""
import json
import gspread
from openai import OpenAI
from google.oauth2.service_account import Credentials
from config import OPENAI_API_KEY, GOOGLE_SERVICE_ACCOUNT_JSON, SPREADSHEET_ID, BRANDS

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_client = OpenAI(api_key=OPENAI_API_KEY)


def generate_ai_title(title: str, summary: str, brand: str) -> str:
    try:
        resp = _client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": f"You generate short punchy headlines under 10 words for brand intel alerts about {brand}. No fluff. Just the key fact."},
                {"role": "user", "content": f"Title: {title}\nSummary: {summary[:500]}"},
            ],
            temperature=0,
            max_tokens=30,
        )
        return resp.choices[0].message.content.strip().strip('"')
    except Exception as e:
        print(f"  [ai] Error: {e}")
        return title[:80]


def backfill_tab(ws, tab_name: str, brand_name: str):
    rows = ws.get_all_records()
    if not rows:
        print(f"  [{tab_name}] No rows found")
        return

    # Find AI Title column index (1-based for gspread)
    headers = ws.row_values(1)
    if "AI Title" not in headers:
        print(f"  [{tab_name}] No 'AI Title' column found — add it first")
        return

    ai_title_col = headers.index("AI Title") + 1  # 1-based

    updated = 0
    for i, row in enumerate(rows, start=2):  # start=2 to skip header
        if row.get("AI Title", "").strip():
            continue  # already has AI title

        title = row.get("Title", "")
        summary = row.get("Summary", "")
        if not title:
            continue

        ai_title = generate_ai_title(title, summary, brand_name)
        ws.update_cell(i, ai_title_col, ai_title)
        print(f"  [{tab_name}] Row {i}: {ai_title}")
        updated += 1

    print(f"  [{tab_name}] Done — {updated} rows updated")


def run():
    creds = Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_JSON, scopes=SCOPES)
    gc = gspread.authorize(creds)
    spreadsheet = gc.open_by_key(SPREADSHEET_ID)

    for brand in BRANDS:
        tab = brand["tab"]
        name = brand["name"]
        print(f"\nBackfilling AI Titles for '{tab}'...")
        try:
            ws = spreadsheet.worksheet(tab)
            backfill_tab(ws, tab, name)
        except gspread.WorksheetNotFound:
            print(f"  [{tab}] Tab not found — skipping")


if __name__ == "__main__":
    run()
