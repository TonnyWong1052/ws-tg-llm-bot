#!/bin/bash
# Navigate to the project root directory
cd "$(dirname "$0")/.." || exit
PROJECT_ROOT=$(pwd)

# Create logs directory if it doesn't exist
mkdir -p logs

# Function to log errors
log_error() {
    local message=$1
    echo "$(date): ERROR - $message" >> logs/error.log
    echo "❌ $message"
}

# Function to log info
log_info() {
    local message=$1
    echo "$(date): INFO - $message" >> logs/bot_run.log
    echo "ℹ️ $message"
}

# Function to check if a process exists
check_process() {
    local pattern=$1
    if pgrep -f "$pattern" > /dev/null; then
        return 0
    else
        return 1
    fi
}

# First determine exactly which Python command is available
log_info "Detecting available Python command..."
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    log_info "Found python3 command"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
    log_info "Found python command"
else
    log_error "No Python interpreter found. Please install Python 3."
    exit 1
fi

# Check Python version to ensure it's 3.x
PYTHON_VERSION=$($PYTHON_CMD --version 2>&1)
log_info "Python version: $PYTHON_VERSION"

# Determine which pip command to use
if command -v pip3 &> /dev/null; then
    PIP_CMD="pip3"
    log_info "Found pip3 command"
elif command -v pip &> /dev/null; then
    PIP_CMD="pip"
    log_info "Found pip command"
else
    log_error "pip not found. Will skip package installation."
    PIP_CMD=""
fi

# Check for any running bot processes and terminate them
if check_process "python.*main.py"; then
    log_info "Found existing bot process. Terminating it..."
    if ! pkill -f "python.*main.py"; then
        log_error "Failed to terminate existing bot process"
        exit 1
    fi
    sleep 5
fi

# Remove journal file if it exists (fixes locked database issues)
if [ -f "session_name.session-journal" ]; then
    log_info "Removing session journal file to prevent database locks..."
    rm session_name.session-journal || {
        log_error "Failed to remove session journal file"
        exit 1
    }
fi

# Make sure the config directory exists
mkdir -p config || {
    log_error "Failed to create config directory"
    exit 1
}

# If .env file exists in root, move it to config directory
if [ -f ".env" ]; then
    log_info "Moving .env file to config directory..."
    mv .env config/.env || {
        log_error "Failed to move .env file"
        exit 1
    }
fi

# Check if the session file exists - if not, try to verify it
if [ ! -f "session_name.session" ]; then
    log_info "Telegram session file not found. Checking if we can create it..."
    
    # Check if we're running interactively
    if [ -t 0 ]; then
        log_info "Running in interactive mode. Will try to create a session file."
        echo "You'll need to enter the code sent to your Telegram app."
        if ! $PYTHON_CMD scripts/setup_session.py; then
            log_error "Failed to create Telegram session file."
            exit 1
        fi
    else
        log_error "Running in non-interactive mode but session file is missing."
        echo "Please run 'python scripts/setup_session.py' on your local machine first,"
        echo "then upload the session_name.session file to your server."
        exit 1
    fi
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
  if ! pgrep -f "python.*main.py" > /dev/null; then
    echo "[\$(date)] Bot process not found, restarting..." >> "\$LOG_DIR/monitor.log"
    # Check for session locks before starting
    check_session_lock
    
    # Start the bot with explicit path to python
    nohup \$PYTHON_CMD \$(pwd)/src/main.py > "\$LOG_DIR/bot_output.log" 2>&1 &
    BOT_PID=\$!
    echo "[\$(date)] Bot restarted with PID \$BOT_PID" >> "\$LOG_DIR/monitor.log"
    
    # Check if the bot started successfully
    sleep 5
    if ! ps -p \$BOT_PID > /dev/null; then
      echo "[\$(date)] Bot failed to start! Check bot_output.log for errors" >> "\$LOG_DIR/monitor.log"
      echo "[\$(date)] Last 20 lines of bot_output.log:" >> "\$LOG_DIR/monitor.log"
      tail -n 20 "\$LOG_DIR/bot_output.log" >> "\$LOG_DIR/monitor.log" 2>&1
      
      # Check for authentication error
      if grep -q "not authorized" "\$LOG_DIR/bot_output.log" || grep -q "EOF when reading a line" "\$LOG_DIR/bot_output.log"; then
        echo "[\$(date)] Authentication error detected. Please create a valid session file using scripts/setup_session.py" >> "\$LOG_DIR/monitor.log"
      fi
    fi
  else
    echo "[\$(date)] Bot is running" >> "\$LOG_DIR/monitor.log"
  fi
  sleep 60  # Check every minute instead of every 5 minutes for quicker response
done
EOF

chmod +x ${PROJECT_ROOT}/scripts/monitor_bot.sh || {
    log_error "Failed to make monitor_bot.sh executable"
    exit 1
}

# Verify session file before starting
log_info "Verifying Telegram session file..."
if ! $PYTHON_CMD scripts/setup_session.py --verify; then
    log_error "Telegram session file verification failed."
    echo "Please run 'python scripts/setup_session.py' to create a valid session."
    exit 1
fi

# Start the bot using nohup
log_info "Starting Telegram bot with nohup using $PYTHON_CMD..."
echo "Full command: nohup $PYTHON_CMD $(pwd)/src/main.py > logs/bot_output.log 2>&1"
nohup $PYTHON_CMD $(pwd)/src/main.py > logs/bot_output.log 2>&1 &
BOT_PID=$!

# Verify the bot started properly
sleep 5
if ! ps -p $BOT_PID > /dev/null; then
    log_error "Bot failed to start! Please check logs/bot_output.log for details"
    echo "Last 20 lines of bot_output.log:"
    tail -n 20 logs/bot_output.log
    
    # Check for authentication error specifically
    if grep -q "not authorized" logs/bot_output.log || grep -q "EOF when reading a line" logs/bot_output.log; then
        log_error "AUTHENTICATION ERROR DETECTED: The bot needs to authenticate with Telegram."
        echo "Please run 'python scripts/setup_session.py' on your local machine first,"
        echo "then upload the session_name.session file to your server."
    fi
    
    exit 1
fi

# Start the monitor script in background
log_info "Starting monitor script..."
nohup bash scripts/monitor_bot.sh > logs/monitor_output.log 2>&1 &
MONITOR_PID=$!

# Create a status checker script
cat > ${PROJECT_ROOT}/scripts/check_status.sh << 'EOF'
#!/bin/bash

cd "$(dirname "$0")/.." || exit

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
tail -n 20 logs/bot_output.log 2>/dev/null || echo "No logs found"

echo ""
echo "=== Latest Monitor Logs ==="
tail -n 10 logs/monitor.log 2>/dev/null || echo "No logs found"

echo ""
echo "=== Session Status ==="
if [ -f "session_name.session" ]; then
    echo "✅ Session file exists"
    stat session_name.session
else
    echo "❌ Session file is missing!"
fi
EOF

chmod +x ${PROJECT_ROOT}/scripts/check_status.sh || {
    log_error "Failed to make check_status.sh executable"
    exit 1
}

# Verify both processes started
log_info "========================================================="
if ps -p $BOT_PID > /dev/null; then
    log_info "✅ Bot started successfully with PID: $BOT_PID"
else
    log_error "❌ Failed to start bot"
fi

if ps -p $MONITOR_PID > /dev/null; then
    log_info "✅ Monitor started successfully with PID: $MONITOR_PID"
else
    log_error "❌ Failed to start monitor"
fi

log_info ""
log_info "To check status: bash scripts/check_status.sh"
log_info "To view bot logs: cat logs/bot_output.log"
log_info "To view monitor logs: cat logs/monitor.log"
log_info "To stop the bot: pkill -f \"python.*main.py\""
log_info "To stop everything: pkill -f \"python.*main.py\"; pkill -f \"monitor_bot.sh\""
log_info "========================================================="