#!/bin/bash

cd "$(dirname "$0")/.." || exit

echo "=== Telegram Bot Status ==="
if pgrep -f "python.*userbot_tg.py" > /dev/null; then
    echo "✅ Bot is running with PID: $(pgrep -f "python.*userbot_tg.py")"
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
echo "Last 20 lines of bot output:"
tail -n 20 logs/bot_output.log 2>/dev/null || echo "No logs found"

echo ""
echo "=== Latest Monitor Logs ==="
echo "Last 10 lines of monitor log:"
tail -n 10 logs/monitor.log 2>/dev/null || echo "No logs found"

echo ""
echo "=== Looking for Errors ==="
echo "Searching for errors in logs:"
grep -i "error\|exception\|failed\|traceback" logs/bot_output.log 2>/dev/null | tail -n 15 || echo "No errors found" 