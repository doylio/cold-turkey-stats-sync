#!/bin/bash
set -euo pipefail

if [ "$(id -u)" -eq 0 ]; then
  echo "Please run this script without sudo (as your user)."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PLIST_DEST="$HOME/Library/LaunchAgents/com.coldturkey.stats-sync.plist"

mkdir -p "$HOME/Library/LaunchAgents"

cat > "$PLIST_DEST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>com.coldturkey.stats-sync</string>

    <key>ProgramArguments</key>
    <array>
      <string>/bin/bash</string>
      <string>-lc</string>
      <string>$REPO_DIR/macos/run_sync.sh</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>StartCalendarInterval</key>
    <dict>
      <key>Hour</key>
      <integer>9</integer>
      <key>Minute</key>
      <integer>0</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>$REPO_DIR/macos/launchd.out.log</string>
    <key>StandardErrorPath</key>
    <string>$REPO_DIR/macos/launchd.err.log</string>
  </dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)" "$PLIST_DEST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_DEST"
launchctl enable "gui/$(id -u)/com.coldturkey.stats-sync"
launchctl kickstart -k "gui/$(id -u)/com.coldturkey.stats-sync"

echo "Installed launchd job: com.coldturkey.stats-sync"
