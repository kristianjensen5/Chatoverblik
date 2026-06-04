#!/bin/bash
# Installerer Chatoverblik som LaunchAgent — så serveren altid kører i baggrunden.
# Du åbner bare http://localhost:7777 i browseren når du vil bruge den.

set -e
cd "$(dirname "$0")"

HERE="$(pwd -P)"
PLIST="$HOME/Library/LaunchAgents/com.kristian.chatoverblik.plist"
LABEL="com.kristian.chatoverblik"
UID_NUM=$(id -u)

# ───── Vælg Python ─────
# Foretrækker system-Python (/usr/bin/python3) fordi launchd håndterer den
# stien stabilt. Falder tilbage til hvad der findes hvis nødvendigt.
PYTHON=""
for candidate in /usr/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  if [ -x "$candidate" ] && "$candidate" -c 'import sys; assert sys.version_info >= (3,9)' 2>/dev/null; then
    PYTHON="$candidate"
    break
  fi
done

if [ -z "$PYTHON" ]; then
  echo "❌ Ingen Python 3.9+ fundet på standardstier."
  exit 1
fi

echo "🐍 Bruger Python: $PYTHON"

# ───── Hent API-key ─────
if [ -z "$ANTHROPIC_API_KEY" ]; then
  if [ -f "$HOME/.zshenv" ]; then
    KEY_FROM_FILE=$(grep -E '^export ANTHROPIC_API_KEY=' "$HOME/.zshenv" | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")
    if [ -n "$KEY_FROM_FILE" ]; then
      export ANTHROPIC_API_KEY="$KEY_FROM_FILE"
    fi
  fi
fi

if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "⚠️  ANTHROPIC_API_KEY ikke fundet."
  echo "   Skriv den her (input skjules):"
  read -s ANTHROPIC_API_KEY
  echo
fi

if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "❌ Stadig ingen API-key. Afbryder."
  exit 1
fi

# ───── Stop evt. tidligere installation grundigt ─────
echo "🧹 Rydder evt. tidligere installation…"
launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null || true
launchctl unload "$PLIST" 2>/dev/null || true
launchctl remove "$LABEL" 2>/dev/null || true
pkill -f "chatoverblik.py" 2>/dev/null || true
sleep 1

# ───── Opret plist ─────
mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$HERE/logs"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON</string>
    <string>$HERE/chatoverblik.py</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$HERE</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ProcessType</key>
  <string>Background</string>
  <key>StandardOutPath</key>
  <string>$HERE/logs/stdout.log</string>
  <key>StandardErrorPath</key>
  <string>$HERE/logs/stderr.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>ANTHROPIC_API_KEY</key>
    <string>$ANTHROPIC_API_KEY</string>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
</dict>
</plist>
EOF

chmod 600 "$PLIST"   # API-key skal kun være læsbar af dig

# ───── Bootstrap (modern launchctl) ─────
echo "🚀 Indlæser i launchd…"
if launchctl bootstrap "gui/$UID_NUM" "$PLIST" 2>&1; then
  echo "   → bootstrap OK"
else
  # Fallback til ældre load-syntax
  if launchctl load "$PLIST" 2>&1; then
    echo "   → load OK (fallback)"
  else
    echo "❌ Kunne ikke indlæse LaunchAgent."
    echo "   Tjek logs: $HERE/logs/stderr.log"
    exit 1
  fi
fi

sleep 2

# ───── Verificer ─────
if pgrep -f "chatoverblik.py" > /dev/null; then
  echo
  echo "✅ Chatoverblik kører nu i baggrunden."
  echo "   Den starter automatisk hver gang du logger ind."
  echo
  echo "   → Åbn:  http://localhost:7777"
  echo
  echo "   Logs:    $HERE/logs/"
  echo "   Stop:    dobbeltklik uninstall-autostart.command"
  open "http://localhost:7777"
else
  echo
  echo "❌ Processen startede ikke. Tjek logs:"
  echo "   $HERE/logs/stderr.log"
  echo
  tail -20 "$HERE/logs/stderr.log" 2>/dev/null
fi
