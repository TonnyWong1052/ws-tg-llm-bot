#!/bin/bash

cd "./.." || exit
LOG_DIR="/Users/tomleung/Downloads/ws-tg-llm-bot/logs"
mkdir -p "$LOG_DIR"
chmod -R 777 "$LOG_DIR"

PYTHON_CMD="python3"

echo "[$(date)] Monitor script started using $PYTHON_CMD" >> "$LOG_DIR/monitor.log"

# Function to check if the session file is locked
check_session_lock() {
  if [ -f "session_name.session-journal" ]; then
    echo "[$(date)] Found locked session file, removing it..." >> "$LOG_DIR/monitor.log"
    rm session_name.session-journal
    return 0
  fi
  return 1
}

while true; do
  if ! pgrep -f "python.*main.py" > /dev/null; then
    echo "[$(date)] Bot process not found, restarting..." >> "$LOG_DIR/monitor.log"
    # Check for session locks before starting
    check_session_lock
    
    # Start the bot with explicit path to python
    nohup $PYTHON_CMD $(pwd)/src/main.py > "$LOG_DIR/bot_output.log" 2>&1 &
    BOT_PID=$!
    echo "[$(date)] Bot restarted with PID $BOT_PID" >> "$LOG_DIR/monitor.log"
    
    # Check if the bot started successfully
    sleep 5
    if ! ps -p $BOT_PID > /dev/null; then
      echo "[$(date)] Bot failed to start! Check bot_output.log for errors" >> "$LOG_DIR/monitor.log"
      echo "[$(date)] Last 20 lines of bot_output.log:" >> "$LOG_DIR/monitor.log"
      tail -n 20 "$LOG_DIR/bot_output.log" >> "$LOG_DIR/monitor.log" 2>&1
      
      # Check for authentication error
      if grep -q "not authorized" "$LOG_DIR/bot_output.log" || grep -q "EOF when reading a line" "$LOG_DIR/bot_output.log"; then
        echo "[$(date)] Authentication error detected. Please create a valid session file using scripts/setup_session.py" >> "$LOG_DIR/monitor.log"
      fi
    fi
  else
    echo "[$(date)] Bot is running" >> "$LOG_DIR/monitor.log"
  fi
  sleep 60  # Check every minute instead of every 5 minutes for quicker response
done
