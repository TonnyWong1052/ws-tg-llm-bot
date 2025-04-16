#!/bin/bash
# Navigate to the project root directory
cd "$(dirname "$0")/.." || exit
PROJECT_ROOT=$(pwd)

# Create logs directory if it doesn't exist
mkdir -p logs

# First determine exactly which Python command is available
echo "Detecting available Python command..."
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    echo "Found python3 command"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
    echo "Found python command"
else
    echo "Error: No Python interpreter found. Please install Python 3."
    echo "This error has been logged to logs/error.log"
    echo "$(date): No Python interpreter found. Please install Python 3." >> logs/error.log
    exit 1
fi

# Check Python version to ensure it's 3.x
PYTHON_VERSION=$($PYTHON_CMD --version 2>&1)
echo "Python version: $PYTHON_VERSION"

# Determine which pip command to use
if command -v pip3 &> /dev/null; then
    PIP_CMD="pip3"
    echo "Found pip3 command"
elif command -v pip &> /dev/null; then
    PIP_CMD="pip"
    echo "Found pip command"
else
    echo "Warning: pip not found. Will skip package installation."
    echo "$(date): Warning: pip not found. Will skip package installation." >> logs/error.log
    PIP_CMD=""
fi

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

# Install required packages if pip is available
if [ -n "$PIP_CMD" ]; then
    echo "Installing required packages using $PIP_CMD..."
    $PIP_CMD install -r requirements.txt --user
else
    echo "Skipping package installation since pip is not available."
fi

# Make sure the config directory exists
mkdir -p config

# If .env file exists in root, move it to config directory
if [ -f ".env" ]; then
    echo "Moving .env file to config directory..."
    mv .env config/.env
fi

# Create a monitoring script to automatically restart the bot if it crashes
cat > ${PROJECT_ROOT}/scripts/monitor_bot.sh << EOF
#!/bin/bash

cd "$(dirname "\$0")/.." || exit
LOG_DIR="logs"
mkdir -p "\$LOG_DIR"

PYTHON_CMD="$PYTHON_CMD"

echo "[\$(date)] Monitor script started using \$PYTHON_CMD" >> "\$LOG_DIR/monitor.log"

# Function to check if the session file is locked
check_session_lock() {
  if [ -f "session_name.session-journal" ]; then
    echo "[\$(date)] Found locked session file, removing it..." >> "\$LOG_DIR/monitor.log"
    rm session_name.session-journal
    return 0
  fi
  return 1
}

while true; do
  if ! pgrep -f "python.*userbot_tg.py" > /dev/null; then
    echo "[\$(date)] Bot process not found, restarting..." >> "\$LOG_DIR/monitor.log"
    # Check for session locks before starting
    check_session_lock
    
    # Start the bot with explicit path to python
    nohup \$PYTHON_CMD \$(pwd)/src/userbot/userbot_tg.py > "\$LOG_DIR/bot_output.log" 2>&1 &
    BOT_PID=\$!
    echo "[\$(date)] Bot restarted with PID \$BOT_PID" >> "\$LOG_DIR/monitor.log"
    
    # Check if the bot started successfully
    sleep 3
    if ! ps -p \$BOT_PID > /dev/null; then
      echo "[\$(date)] Bot failed to start! Check bot_output.log for errors" >> "\$LOG_DIR/monitor.log"
      echo "[\$(date)] Last 10 lines of bot_output.log:" >> "\$LOG_DIR/monitor.log"
      tail -n 10 "\$LOG_DIR/bot_output.log" >> "\$LOG_DIR/monitor.log" 2>&1
    fi
  else
    echo "[\$(date)] Bot is running" >> "\$LOG_DIR/monitor.log"
  fi
  sleep 60  # Check every minute instead of every 5 minutes for quicker response
done
EOF

chmod +x ${PROJECT_ROOT}/scripts/monitor_bot.sh

# Start the bot using nohup
echo "Starting Telegram bot with nohup using $PYTHON_CMD..."
echo "Full command: nohup $PYTHON_CMD $(pwd)/src/userbot/userbot_tg.py > logs/bot_output.log 2>&1"
nohup $PYTHON_CMD $(pwd)/src/userbot/userbot_tg.py > logs/bot_output.log 2>&1 &
BOT_PID=$!

# Verify the bot started properly
sleep 3
if ! ps -p $BOT_PID > /dev/null; then
    echo "❌ Bot failed to start! Please check logs/bot_output.log for details"
    echo "Last 10 lines of bot_output.log:"
    tail -n 10 logs/bot_output.log
    exit 1
fi

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
tail -n 20 logs/bot_output.log 2>/dev/null || echo "No logs found"

echo ""
echo "=== Latest Monitor Logs ==="
tail -n 10 logs/monitor.log 2>/dev/null || echo "No logs found"
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