#!/bin/bash

cd "$(dirname "$0")/.." || exit
LOG_DIR="$LOG_DIR"

echo "=== Telegram Bot Status ==="
if pgrep -f "python.*main.py" > /dev/null; then
    echo "✅ Bot is running with PID: $(pgrep -f "python.*main.py")"
else
    echo "❌ Bot is NOT running!"
fi

if pgrep -f "monitor_bot.sh" > /dev/null; then
    echo "✅ Monitor script is running with PID: $(pgrep -f "monitor_bot.sh")"
else
    echo "❌ Monitor script is NOT running!"
fi

echo ""
echo "=== Latest Bot Logs ==="
tail -n 20 "$LOG_DIR/bot_output.log" 2>/dev/null || echo "No logs found"

echo ""
echo "=== Latest Monitor Logs ==="
tail -n 10 "$LOG_DIR/monitor.log" 2>/dev/null || echo "No logs found"

echo ""
echo "=== Session Status ==="
if [ -f "session_name.session" ]; then
    echo "✅ Session file exists"
    stat session_name.session
else
    echo "❌ Session file is missing!"
fi
