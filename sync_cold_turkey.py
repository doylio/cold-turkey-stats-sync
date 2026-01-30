#!/usr/bin/env python3
import json
import os
import sqlite3
from datetime import datetime, timezone, date, time
from urllib.parse import urlparse

from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

DEFAULT_WORKSHEET = "Raw Data"
DEFAULT_CURSOR_PATH = ".sync_cursor.json"


def load_config():
    load_dotenv()
    db_path = os.getenv("COLD_TURKEY_DB_PATH")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    worksheet = os.getenv("GOOGLE_SHEET_WORKSHEET", DEFAULT_WORKSHEET)
    creds_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    cursor_path = os.getenv("SYNC_CURSOR_PATH", DEFAULT_CURSOR_PATH)

    missing = []
    if not db_path:
        missing.append("COLD_TURKEY_DB_PATH")
    if not sheet_id:
        missing.append("GOOGLE_SHEET_ID")
    if not creds_path:
        missing.append("GOOGLE_SERVICE_ACCOUNT_JSON")

    if missing:
        raise ValueError("Missing required env vars: " + ", ".join(missing))

    return {
        "db_path": db_path,
        "sheet_id": sheet_id,
        "worksheet": worksheet,
        "creds_path": creds_path,
        "cursor_path": cursor_path,
    }


def normalize_domain(raw: str) -> str:
    if not raw:
        return ""
    # Cold Turkey stores without protocol; urlparse needs a scheme or //
    candidate = raw.strip()
    if "//" not in candidate:
        candidate = "//" + candidate
    parsed = urlparse(candidate)
    host = parsed.netloc or parsed.path.split("/")[0]
    return host.lower()


def read_cursor(cursor_path: str) -> str | None:
    if not os.path.exists(cursor_path):
        return None
    try:
        with open(cursor_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("last_synced_date")
    except (OSError, json.JSONDecodeError):
        return None


def write_cursor(cursor_path: str, last_date: str) -> None:
    data = {"last_synced_date": last_date}
    with open(cursor_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def local_date_from_timestamp(ts: float) -> str:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone()
    return dt.date().isoformat()


def start_of_next_day_epoch(local_date_str: str) -> float:
    local_day = date.fromisoformat(local_date_str)
    next_day = local_day.toordinal() + 1
    next_date = date.fromordinal(next_day)
    local_tz = datetime.now().astimezone().tzinfo
    local_start = datetime.combine(next_date, time.min, tzinfo=local_tz)
    return local_start.timestamp()


def fetch_stats(db_path: str, min_ts: float | None) -> list[tuple[float, str, float]]:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        if min_ts is not None:
            cur.execute("SELECT date, domain, seconds FROM stats WHERE date >= ?", (min_ts,))
        else:
            cur.execute("SELECT date, domain, seconds FROM stats")
        return cur.fetchall()
    finally:
        conn.close()


def aggregate_stats(rows: list[tuple[float, str, float]]) -> dict[tuple[str, str], float]:
    aggregated: dict[tuple[str, str], float] = {}
    for ts, raw_domain, seconds in rows:
        local_day = local_date_from_timestamp(ts)
        domain = normalize_domain(raw_domain)
        if not domain:
            continue
        key = (local_day, domain)
        aggregated[key] = aggregated.get(key, 0.0) + float(seconds)
    return aggregated


def build_sheets_service(creds_path: str):
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    return build("sheets", "v4", credentials=creds)


def ensure_headers(service, sheet_id: str, worksheet: str) -> None:
    range_name = f"{worksheet}!A1:C1"
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=range_name,
    ).execute()
    values = result.get("values", [])
    if not values:
        service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range=range_name,
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [["Domain", "Date", "Minutes"]]},
        ).execute()
    ensure_date_column_date_format(service, sheet_id, worksheet)


def get_sheet_id(service, sheet_id: str, worksheet: str) -> int | None:
    meta = service.spreadsheets().get(
        spreadsheetId=sheet_id,
        fields="sheets(properties(sheetId,title))",
    ).execute()
    for sheet in meta.get("sheets", []):
        props = sheet.get("properties", {})
        if props.get("title") == worksheet:
            return props.get("sheetId")
    return None


def ensure_date_column_date_format(service, sheet_id: str, worksheet: str) -> None:
    gid = get_sheet_id(service, sheet_id, worksheet)
    if gid is None:
        return
    body = {
        "requests": [
            {
                "repeatCell": {
                    "range": {
                        "sheetId": gid,
                        "startColumnIndex": 1,
                        "endColumnIndex": 2,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "numberFormat": {"type": "DATE", "pattern": "yyyy-mm-dd"}
                        }
                    },
                    "fields": "userEnteredFormat.numberFormat",
                }
            }
        ]
    }
    service.spreadsheets().batchUpdate(spreadsheetId=sheet_id, body=body).execute()


def append_rows(service, sheet_id: str, worksheet: str, rows: list[list[str | float]]):
    range_name = f"{worksheet}!A:C"
    service.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range=range_name,
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": rows},
    ).execute()


def main():
    config = load_config()

    last_synced = read_cursor(config["cursor_path"])
    min_ts = None
    if last_synced:
        min_ts = start_of_next_day_epoch(last_synced)

    rows = fetch_stats(config["db_path"], min_ts)
    aggregated = aggregate_stats(rows)

    if not aggregated:
        print("No new data to sync.")
        return

    today_local = datetime.now().astimezone().date().isoformat()
    sorted_items = sorted(aggregated.items(), key=lambda item: (item[0][0], item[0][1]))
    output_rows: list[list[str | float]] = []
    max_date = last_synced

    for (local_day, domain), seconds in sorted_items:
        if local_day == today_local:
            continue
        minutes = round(seconds / 60.0, 2)
        output_rows.append([domain, local_day, minutes])
        if not max_date or local_day > max_date:
            max_date = local_day

    if not output_rows:
        print("No completed days to sync yet.")
        return

    service = build_sheets_service(config["creds_path"])
    ensure_headers(service, config["sheet_id"], config["worksheet"])
    append_rows(service, config["sheet_id"], config["worksheet"], output_rows)

    if max_date:
        write_cursor(config["cursor_path"], max_date)

    print(f"Synced {len(output_rows)} rows through {max_date}.")


if __name__ == "__main__":
    main()
