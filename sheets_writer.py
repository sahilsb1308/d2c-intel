import gspread
from google.oauth2.service_account import Credentials
from config import GOOGLE_SERVICE_ACCOUNT_JSON, SPREADSHEET_ID

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = ["Title", "Category", "Source", "Summary", "Link", "Sentiment", "Date Added"]

CATEGORY_COLORS = {
    "Product Review":     {"red": 0.8,  "green": 0.9,  "blue": 1.0},
    "Customer Complaint": {"red": 1.0,  "green": 0.8,  "blue": 0.8},
    "Recommendation":     {"red": 0.8,  "green": 1.0,  "blue": 0.8},
    "Partnership":        {"red": 0.85, "green": 0.75, "blue": 1.0},
    "Campaign":           {"red": 1.0,  "green": 0.95, "blue": 0.7},
    "News Coverage":      {"red": 0.95, "green": 0.95, "blue": 0.95},
    "Thought Leadership": {"red": 1.0,  "green": 0.88, "blue": 0.8},
    "General Mention":    {"red": 1.0,  "green": 1.0,  "blue": 1.0},
}

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
    ws.format("A1:E1", {
        "textFormat": {"bold": True, "fontSize": 11},
        "backgroundColor": {"red": 0.13, "green": 0.13, "blue": 0.13},
        "horizontalAlignment": "CENTER",
        "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
    })
    spreadsheet.batch_update({"requests": [
        # Column widths
        *[{
            "updateDimensionProperties": {
                "range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
                "properties": {"pixelSize": size},
                "fields": "pixelSize",
            }
        } for i, size in enumerate([280, 160, 100, 520, 320])],
        # Category dropdown on column B
        {
            "setDataValidation": {
                "range": {"sheetId": ws.id, "startRowIndex": 1, "endRowIndex": 2000, "startColumnIndex": 1, "endColumnIndex": 2},
                "rule": {
                    "condition": {
                        "type": "ONE_OF_LIST",
                        "values": [{"userEnteredValue": c} for c in CATEGORY_COLORS.keys()],
                    },
                    "showCustomUi": True,
                    "strict": True,
                }
            }
        },
    ]})


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

    # Format each new row
    requests = []
    for i, m in enumerate(mentions):
        r = next_row + i
        color = CATEGORY_COLORS.get(m.get("category", "General Mention"), CATEGORY_COLORS["General Mention"])

        # Category cell (col B = index 1) — colored background, bold, centered
        requests.append({"repeatCell": {
            "range": {"sheetId": ws.id, "startRowIndex": r - 1, "endRowIndex": r, "startColumnIndex": 1, "endColumnIndex": 2},
            "cell": {"userEnteredFormat": {
                "backgroundColor": color,
                "horizontalAlignment": "CENTER",
                "textFormat": {"bold": True},
                "wrapStrategy": "WRAP",
            }},
            "fields": "userEnteredFormat(backgroundColor,horizontalAlignment,textFormat,wrapStrategy)",
        }})

        # Summary cell (col D = index 3) — wrap + top align
        requests.append({"repeatCell": {
            "range": {"sheetId": ws.id, "startRowIndex": r - 1, "endRowIndex": r, "startColumnIndex": 3, "endColumnIndex": 4},
            "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}},
            "fields": "userEnteredFormat(wrapStrategy,verticalAlignment)",
        }})

    if requests:
        ws.spreadsheet.batch_update({"requests": requests})

    print(f"  [sheets] Wrote {len(rows)} rows to tab '{tab_name}'")
