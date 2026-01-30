# Cold Turkey Stats Sync

Sync Cold Turkey browser stats into a Google Sheet.

## Setup

1. Create a Google Cloud service account and download its JSON key.
2. Share your Google Sheet with the service account email.
3. Create `.env` from `.env.example` and fill in values.

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

This will run the sync once at login and once daily at 9:00 local time.

```bash
./macos/setup_launchd.sh
```

Useful commands:

```bash
launchctl list | grep com.coldturkey.stats-sync
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.coldturkey.stats-sync.plist
```

## Notes

- Data is aggregated by local date and domain, then appended to the `Raw Data` worksheet.
- A cursor file stores the last synced local date to keep syncs incremental.
