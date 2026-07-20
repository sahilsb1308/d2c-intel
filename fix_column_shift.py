"""
One-time fix: existing data rows were written before AI Title column was added.
This inserts an empty AI Title cell into each existing row so data aligns with headers.

Run once: python fix_column_shift.py
"""
import gspread
from google.oauth2.service_account import Credentials
from config import GOOGLE_SERVICE_ACCOUNT_JSON, SPREADSHEET_ID, BRANDS

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

EXPECTED_HEADERS = ["Title", "AI Title", "Category", "Source", "Summary", "Link", "Sentiment", "Date Added"]
OLD_HEADERS     = ["Title", "Category", "Source", "Summary", "Link", "Sentiment", "Date Added"]


def fix_tab(ws, tab_name: str):
    all_rows = ws.get_all_values()
    if len(all_rows) < 2:
        print(f"  [{tab_name}] No data rows — skipping")
        return

    headers = all_rows[0]

    # Check if AI Title column already exists in the right place
    if len(headers) >= 2 and headers[1] == "AI Title":
        # Headers look right — check if data rows are aligned
        # A misaligned row has Category value in AI Title column (e.g. "Partnership", "News Coverage")
        categories = {"Product Review", "Customer Complaint", "Recommendation",
                      "Partnership", "Campaign", "News Coverage", "Thought Leadership", "General Mention"}
        misaligned_count = sum(
            1 for row in all_rows[1:]
            if len(row) >= 2 and row[1] in categories
        )

        if not misaligned_count:
            print(f"  [{tab_name}] Already aligned — skipping")
            return

        print(f"  [{tab_name}] {misaligned_count} misaligned rows — fixing...")

        data_rows = all_rows[1:]
        fixed_rows = []
        for row in data_rows:
            if len(row) >= 2 and row[1] in categories:
                # Old format: [Title, Category, Source, Summary, Link, Sentiment, Date]
                # Insert empty AI Title at index 1 so everything aligns to new headers
                fixed = [row[0], ""] + row[1:]
            else:
                fixed = row
            fixed_rows.append(fixed)

        # Clear existing data (keep header) and rewrite
        last_col = chr(ord('A') + len(EXPECTED_HEADERS) - 1)
        last_row = 1 + len(data_rows)
        ws.batch_clear([f"A2:{last_col}{last_row}"])

        if fixed_rows:
            ws.update(f"A2", fixed_rows, value_input_option="USER_ENTERED")

        print(f"  [{tab_name}] Fixed {len(data_rows)} rows")

    else:
        print(f"  [{tab_name}] Header doesn't have AI Title in column B — check manually")
        print(f"  [{tab_name}] Current headers: {headers}")


def run():
    creds = Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_JSON, scopes=SCOPES)
    gc = gspread.authorize(creds)
    ss = gc.open_by_key(SPREADSHEET_ID)

    for brand in BRANDS:
        tab = brand["tab"]
        print(f"\nChecking '{tab}'...")
        try:
            ws = ss.worksheet(tab)
            fix_tab(ws, tab)
        except gspread.WorksheetNotFound:
            print(f"  [{tab}] Tab not found — skipping")

    print("\nDone. Run backfill_ai_titles.py next to populate the empty AI Title cells.")


if __name__ == "__main__":
    run()
