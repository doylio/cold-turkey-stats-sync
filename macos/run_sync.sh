#!/bin/bash
set -euo pipefail

# Get the absolute path to the repo directory
# Use $0 instead of ${BASH_SOURCE[0]} for better compatibility with bash -lc
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_DIR"

# Function to check network connectivity
check_network() {
  # Try to reach Google DNS, common connectivity check
  if ping -c 1 -W 5 8.8.8.8 >/dev/null 2>&1; then
    return 0
  fi
  # Also try to resolve a hostname
  if host -W 5 google.com >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

# Wait for network to be available (up to 60 seconds)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Checking network connectivity..."
for i in {1..12}; do
  if check_network; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Network is available"
    break
  fi
  if [ $i -eq 12 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Network not available after 60 seconds" >&2
    exit 1
  fi
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting for network... ($i/12)"
  sleep 5
done

# Ensure virtual environment exists and is activated
if [ ! -f ".venv/bin/activate" ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Virtual environment not found at .venv/" >&2
  exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Activating virtual environment..."
source ".venv/bin/activate"

# Verify python-dotenv is installed
if ! python -c "import dotenv" 2>/dev/null; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: python-dotenv not installed in virtual environment" >&2
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Run: pip install -r requirements.txt" >&2
  exit 1
fi

# Run the sync script with retry logic
MAX_RETRIES=3
RETRY_DELAY=30

for attempt in $(seq 1 $MAX_RETRIES); do
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Running sync (attempt $attempt/$MAX_RETRIES)..."

  if ./sync_cold_turkey.py; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Sync completed successfully"
    exit 0
  fi

  EXIT_CODE=$?
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Sync failed with exit code $EXIT_CODE" >&2

  if [ $attempt -lt $MAX_RETRIES ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Retrying in $RETRY_DELAY seconds..."
    sleep $RETRY_DELAY
  fi
done

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Sync failed after $MAX_RETRIES attempts" >&2
exit 1
