# Cold Turkey Stats Sync

Sync Cold Turkey browser stats into a Google Sheet.

## What it does

- Reads the Cold Turkey browsing statistics
- Aggregates by domain and date
- Pushes changes incrementally to a Google Sheet

## Requirements

- Python 3.10+
- A Google Sheet you own
- A Google Cloud service account JSON key

## Google Sheets setup (service account)

1. Create a Google Cloud project (or use an existing one).
2. Enable the Google Sheets API.
3. Create a service account and download its JSON key.
4. Share your Google Sheet with the service account email (Editor access).

## Configure

Copy the example env file and edit it:

```bash
cp .env.example .env
```

Required values:

- `COLD_TURKEY_DB_PATH` (path to the Cold Turkey sqlite file, on MacOS this is likely "/Library/Application Support/Cold Turkey/data-browser.db")
- `GOOGLE_SHEET_ID` (the sheet ID from the URL)
- `GOOGLE_SERVICE_ACCOUNT_JSON` (path to the JSON key file)

Optional:

- `GOOGLE_SHEET_WORKSHEET` (defaults to `Raw Data`)
- `SYNC_CURSOR_PATH` (defaults to `.sync_cursor.json`)

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
./sync_cold_turkey.py
```

## macOS launchd setup

This installs a LaunchAgent that runs at login and daily at 12:01 AM local time.

```bash
./macos/setup_launchd.sh
```

Check status/logs:

```bash
launchctl list | grep com.coldturkey.stats-sync
tail -n 200 /Users/shawn/coding/cold-turkey-stats-sync/macos/launchd.out.log
tail -n 200 /Users/shawn/coding/cold-turkey-stats-sync/macos/launchd.err.log
```

Uninstall:

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.coldturkey.stats-sync.plist
rm -f ~/Library/LaunchAgents/com.coldturkey.stats-sync.plist
```

## Troubleshooting

- If the script says “No completed days to sync yet,” it is skipping the current day by design.
- If LaunchAgent commands fail, ensure `~/Library/LaunchAgents` is owned by your user.
