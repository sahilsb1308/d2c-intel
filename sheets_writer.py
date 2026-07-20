import gspread
from google.oauth2.service_account import Credentials
from config import GOOGLE_SERVICE_ACCOUNT_JSON, SPREADSHEET_ID

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = ["Title", "Category", "Source", "Summary", "Link", "Sentiment", "Date Added"]

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

    # Add header if tab is empty or header row is missing
    first_row = ws.row_values(1)
    if not first_row or first_row[0] != HEADERS[0]:
        _init_header(ws, spreadsheet)

    return ws


def _init_header(ws, spreadsheet):
    ws.append_row(HEADERS)


def get_existing_links(tab_name: str) -> set:
    ws = _get_or_create_tab(tab_name)
    try:
        return set(ws.col_values(5)[1:])  # Column E = Link
    except Exception:
        return set()




def append_mentions(tab_name: str, mentions: list[dict]):
    if not mentions:
        return
    ws = _get_or_create_tab(tab_name)
    next_row = len(ws.get_all_values()) + 1

    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    rows = [[
        m.get("title", ""),
        m.get("category", "General Mention"),
        m.get("platform", tab_name),
        m.get("summary", ""),
        m.get("url", ""),
        m.get("sentiment", "").capitalize(),
        today,
    ] for m in mentions]

    ws.append_rows(rows, value_input_option="USER_ENTERED")

    print(f"  [sheets] Wrote {len(rows)} rows to tab '{tab_name}'")
