#!/bin/bash
# Stopper Chatoverblik og fjerner LaunchAgent.
# Du kan stadig starte den manuelt med start.command bagefter.

set -e
PLIST="$HOME/Library/LaunchAgents/com.kristian.chatoverblik.plist"
LABEL="com.kristian.chatoverblik"
UID_NUM=$(id -u)

launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null || true
launchctl unload "$PLIST" 2>/dev/null || true
launchctl remove "$LABEL" 2>/dev/null || true
pkill -f "chatoverblik.py" 2>/dev/null || true

[ -f "$PLIST" ] && rm -f "$PLIST"

echo "✅ Autostart fjernet. Chatoverblik kører ikke længere automatisk."
echo "   Du kan stadig starte den manuelt med start.command."
