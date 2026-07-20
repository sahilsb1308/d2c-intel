import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta, timezone
from config import GOOGLE_SERVICE_ACCOUNT_JSON, SPREADSHEET_ID

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = ["Title", "AI Title", "Category", "Source", "Summary", "Link", "Sentiment", "Date Added"]

IST = timezone(timedelta(hours=5, minutes=30))

_gc = None


def _get_gc():
    global _gc
    if _gc is None:
        creds = Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_JSON, scopes=SCOPES)
        _gc = gspread.authorize(creds)
    return _gc


def _get_or_create_tab(tab_name: str):
    gc = _get_gc()
    spreadsheet = gc.open_by_key(SPREADSHEET_ID)
    try:
        ws = spreadsheet.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=tab_name, rows=2000, cols=len(HEADERS))

    first_row = ws.row_values(1)
    if list(first_row[:len(HEADERS)]) != HEADERS:
        ws.update("A1", [HEADERS])

    return ws


def _get_header_map(ws) -> dict:
    """Returns {column_name: 1-based_index} from the sheet's actual header row."""
    headers = ws.row_values(1)
    return {h.strip(): i + 1 for i, h in enumerate(headers) if h.strip()}


def get_existing_links(tab_name: str) -> set:
    ws = _get_or_create_tab(tab_name)
    try:
        header_map = _get_header_map(ws)
        link_col = header_map.get("Link")
        if not link_col:
            return set()
        return set(v for v in ws.col_values(link_col)[1:] if v)
    except Exception:
        return set()


def append_mentions(tab_name: str, mentions: list[dict]):
    if not mentions:
        return
    ws = _get_or_create_tab(tab_name)
    header_map = _get_header_map(ws)
    today = datetime.now(IST).strftime("%Y-%m-%d")

    # Map each mention to the sheet's actual column order
    field_map = {
        "Title":      lambda m: m.get("title", ""),
        "AI Title":   lambda m: m.get("ai_title", ""),
        "Category":   lambda m: m.get("category", "General Mention"),
        "Source":     lambda m: m.get("platform", tab_name),
        "Summary":    lambda m: m.get("summary", ""),
        "Link":       lambda m: m.get("url", ""),
        "Sentiment":  lambda m: m.get("sentiment", "").capitalize(),
        "Date Added": lambda m: m.get("published_date") or today,
    }

    num_cols = max(header_map.values())
    rows = []
    for m in mentions:
        row = [""] * num_cols
        for col_name, col_idx in header_map.items():
            if col_name in field_map:
                row[col_idx - 1] = field_map[col_name](m)
        rows.append(row)

    ws.append_rows(rows, value_input_option="USER_ENTERED")
    print(f"  [sheets] Wrote {len(rows)} rows to tab '{tab_name}'")
