#!/bin/bash

# Navigate to the project root directory
cd "$(dirname "$0")/.." || exit
PROJECT_ROOT=$(pwd)

# Make directories for logs if they don't exist
mkdir -p logs

# Check for any running bot processes and terminate them
if pgrep -f "python.*userbot_tg.py" > /dev/null; then
    echo "Found existing bot process. Terminating it..."
    pkill -f "python.*userbot_tg.py"
    sleep 5
fi

# Remove journal file if it exists (fixes locked database issues)
if [ -f "session_name.session-journal" ]; then
    echo "Removing session journal file to prevent database locks..."
    rm session_name.session-journal
fi

# Install required packages
echo "Installing required packages..."
pip install -r requirements.txt --user

# Make sure the config directory exists
mkdir -p config

# If .env file exists in root, move it to config directory
if [ -f ".env" ]; then
    echo "Moving .env file to config directory..."
    mv .env config/.env
fi

# Create a monitoring script to automatically restart the bot if it crashes
cat > ${PROJECT_ROOT}/scripts/monitor_bot.sh << 'EOF'
#!/bin/bash

cd "$(dirname "$0")/.." || exit
LOG_DIR="logs"
mkdir -p "$LOG_DIR"

echo "[$(date)] Monitor script started" >> "$LOG_DIR/monitor.log"

while true; do
  if ! pgrep -f "python.*userbot_tg.py" > /dev/null; then
    echo "[$(date)] Bot process not found, restarting..." >> "$LOG_DIR/monitor.log"
    nohup python src/userbot/userbot_tg.py > "$LOG_DIR/bot_output.log" 2>&1 &
    BOT_PID=$!
    echo "[$(date)] Bot restarted with PID $BOT_PID" >> "$LOG_DIR/monitor.log"
  else
    echo "[$(date)] Bot is running" >> "$LOG_DIR/monitor.log"
  fi
  sleep 300  # Check every 5 minutes
done
EOF

chmod +x ${PROJECT_ROOT}/scripts/monitor_bot.sh

# Start the bot using nohup
echo "Starting Telegram bot with nohup..."
nohup python src/userbot/userbot_tg.py > logs/bot_output.log 2>&1 &
BOT_PID=$!

# Start the monitor script in background
echo "Starting monitor script..."
nohup bash scripts/monitor_bot.sh > logs/monitor_output.log 2>&1 &
MONITOR_PID=$!

# Create a status checker script
cat > ${PROJECT_ROOT}/scripts/check_status.sh << 'EOF'
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
tail -n 20 logs/bot_output.log

echo ""
echo "=== Latest Monitor Logs ==="
tail -n 10 logs/monitor.log
EOF

chmod +x ${PROJECT_ROOT}/scripts/check_status.sh

# Verify both processes started
echo ""
echo "========================================================="
if ps -p $BOT_PID > /dev/null; then
    echo "✅ Bot started successfully with PID: $BOT_PID"
else
    echo "❌ Failed to start bot"
fi

if ps -p $MONITOR_PID > /dev/null; then
    echo "✅ Monitor started successfully with PID: $MONITOR_PID"
else
    echo "❌ Failed to start monitor"
fi

echo ""
echo "To check status: bash scripts/check_status.sh"
echo "To view bot logs: cat logs/bot_output.log"
echo "To view monitor logs: cat logs/monitor.log"
echo "To stop the bot: pkill -f \"python.*userbot_tg.py\""
echo "To stop everything: pkill -f \"python.*userbot_tg.py\"; pkill -f \"monitor_bot.sh\""
echo "========================================================="