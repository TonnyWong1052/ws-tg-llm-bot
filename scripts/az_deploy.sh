#!/bin/bash

# Navigate to the project root directory
cd "$(dirname "$0")/.." || exit
PROJECT_ROOT=$(pwd)

# Create logs directory if it doesn't exist
mkdir -p logs

# Add error logging function
log_error() {
    echo "$(date): ERROR: $1" | tee -a logs/error.log
    echo "❌ $1"
}

log_info() {
    echo "$(date): INFO: $1" | tee -a logs/info.log
    echo "✅ $1"
}

log_warning() {
    echo "$(date): WARNING: $1" | tee -a logs/warning.log
    echo "⚠️ $1"
}

# Determine which Python and pip commands to use
log_info "Detecting available Python command..."
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    log_info "Found python3 command"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
    log_info "Found python command"
else
    log_error "Neither python3 nor python was found. Please install Python."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$($PYTHON_CMD --version)
log_info "Python version: $PYTHON_VERSION"

# Check if the Python version is adequate - fixed comparison to correctly handle version numbers
PYTHON_VERSION_NUMBER=$(echo $PYTHON_VERSION | grep -oE '[0-9]+\.[0-9]+')
PYTHON_MAJOR=$(echo $PYTHON_VERSION_NUMBER | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION_NUMBER | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || [ "$PYTHON_MAJOR" -eq 3 -a "$PYTHON_MINOR" -lt 8 ]; then
    log_error "Python version $PYTHON_VERSION_NUMBER is too old. Need 3.8 or newer."
    exit 1
fi
log_info "Python $PYTHON_VERSION_NUMBER meets requirements (3.8 or newer)"

# Determine which pip command to use
log_info "Detecting available pip command..."
if command -v pip3 &> /dev/null; then
    PIP_CMD="pip3"
    log_info "Found pip3 command"
elif command -v pip &> /dev/null; then
    PIP_CMD="pip"
    log_info "Found pip command"
else
    log_error "Neither pip3 nor pip was found. Please install pip."
    exit 1
fi

log_info "Using Python command: $PYTHON_CMD"
log_info "Using pip command: $PIP_CMD"

# Check for any running bot processes and terminate them
if pgrep -f "python.*userbot_tg.py" > /dev/null; then
    log_info "Found existing bot process. Terminating it..."
    pkill -f "python.*userbot_tg.py"
    sleep 5
fi

# Remove journal file if it exists (fixes locked database issues)
if [ -f "session_name.session-journal" ]; then
    log_info "Removing session journal file to prevent database locks..."
    rm session_name.session-journal
fi

# Install required packages
log_info "Installing required packages..."
$PIP_CMD install -r requirements.txt --user || {
    log_error "Failed to install required packages"
}

# Make sure the config directory exists
mkdir -p config

# Verify .env configuration
if [ -f "config/.env" ]; then
    log_info "Found config/.env file"
else
    if [ -f ".env" ]; then
        log_info "Moving .env file to config directory..."
        mv .env config/.env
        log_info "Moved .env file to config directory"
    else
        log_error "No .env file found in either root or config directory"
        log_warning "Missing required configuration. Please create a config/.env file with API keys."
        # Create sample .env file to help the user
        echo "# Sample .env file - please fill with your actual values" > config/.env.sample
        echo "API_ID=your_telegram_api_id" >> config/.env.sample
        echo "API_HASH=your_telegram_api_hash" >> config/.env.sample
        echo "PHONE_NUMBER=your_phone_number" >> config/.env.sample
        echo "ENVIRONMENT=prod" >> config/.env.sample
        echo "DEEPSEEK_API_KEY=your_deepseek_key" >> config/.env.sample
        echo "GITHUB_API_KEY=your_github_key" >> config/.env.sample
        echo "GROK_API_KEY=your_grok_key" >> config/.env.sample
        log_info "Created config/.env.sample for reference"
    fi
fi

# Verify that the bot script exists and is readable
if [ ! -f "src/userbot/userbot_tg.py" ]; then
    log_error "Bot script not found at src/userbot/userbot_tg.py"
    log_info "Current directory: $(pwd)"
    log_info "Directory listing of src/userbot/:"
    ls -la src/userbot/ || log_error "Cannot access src/userbot directory"
    exit 1
fi

log_info "Verifying bot script is readable..."
if ! $PYTHON_CMD -m py_compile src/userbot/userbot_tg.py; then
    log_error "Bot script has syntax errors. Please fix before starting."
    exit 1
fi
log_info "Bot script syntax check passed"

# Create a monitoring script with enhanced debugging
cat > ${PROJECT_ROOT}/scripts/monitor_bot.sh << EOF
#!/bin/bash

cd "\$(dirname "\$0")/.." || exit
LOG_DIR="logs"
mkdir -p "\$LOG_DIR"

PYTHON_CMD="$PYTHON_CMD"

echo "[\$(date)] Monitor script started using \$PYTHON_CMD" >> "\$LOG_DIR/monitor.log"

# Function to check for and fix potential issues
fix_issues() {
  # Remove journal file if it exists
  if [ -f "session_name.session-journal" ]; then
    echo "[\$(date)] Removing session journal file to prevent database locks..." >> "\$LOG_DIR/monitor.log"
    rm session_name.session-journal
  fi
}

# Function to gather debug info
gather_debug() {
  echo "[\$(date)] --- COLLECTING DEBUG INFO ---" >> "\$LOG_DIR/debug.log"
  echo "Current directory: \$(pwd)" >> "\$LOG_DIR/debug.log"
  echo "Python version: \$($PYTHON_CMD --version 2>&1)" >> "\$LOG_DIR/debug.log"
  echo "Directory listing:" >> "\$LOG_DIR/debug.log"
  ls -la >> "\$LOG_DIR/debug.log"
  echo "Config directory:" >> "\$LOG_DIR/debug.log"
  ls -la config/ >> "\$LOG_DIR/debug.log" 2>&1
  echo ".env file exists: \$(test -f config/.env && echo Yes || echo No)" >> "\$LOG_DIR/debug.log"
  echo "Disk space:" >> "\$LOG_DIR/debug.log"
  df -h >> "\$LOG_DIR/debug.log"
  echo "Memory usage:" >> "\$LOG_DIR/debug.log"
  free -m >> "\$LOG_DIR/debug.log" 2>&1
  echo "Network connectivity:" >> "\$LOG_DIR/debug.log"
  ping -c 3 api.telegram.org >> "\$LOG_DIR/debug.log" 2>&1
  echo "[\$(date)] --- END DEBUG INFO ---" >> "\$LOG_DIR/debug.log"
}

while true; do
  if ! pgrep -f "python.*userbot_tg.py" > /dev/null; then
    echo "[\$(date)] Bot process not found, restarting..." >> "\$LOG_DIR/monitor.log"
    
    # Fix any issues before starting
    fix_issues
    
    # Collect debug info before restart
    gather_debug
    
    # Start with full path to avoid directory issues
    cd "\$(dirname "\$0")/.." || exit
    echo "[\$(date)] Starting bot with command: \$PYTHON_CMD \$(pwd)/src/userbot/userbot_tg.py" >> "\$LOG_DIR/monitor.log"
    nohup \$PYTHON_CMD "\$(pwd)/src/userbot/userbot_tg.py" > "\$LOG_DIR/bot_output.log" 2>&1 &
    BOT_PID=\$!
    echo "[\$(date)] Bot restarted with PID \$BOT_PID" >> "\$LOG_DIR/monitor.log"
    
    # Check if bot started successfully
    sleep 5
    if ! ps -p \$BOT_PID > /dev/null; then
      echo "[\$(date)] Bot failed to start properly. Check logs for errors." >> "\$LOG_DIR/monitor.log"
      echo "[\$(date)] Last 20 lines of bot_output.log:" >> "\$LOG_DIR/monitor.log"
      tail -n 20 "\$LOG_DIR/bot_output.log" >> "\$LOG_DIR/monitor.log" 2>&1
    fi
  else
    echo "[\$(date)] Bot is running" >> "\$LOG_DIR/monitor.log"
  fi
  sleep 60  # Check every minute
done
EOF

chmod +x ${PROJECT_ROOT}/scripts/monitor_bot.sh

# Check if we can access the .env file
if [ -f "config/.env" ]; then
    log_info "Testing .env file readability..."
    if grep -q "API_ID" "config/.env"; then
        log_info ".env file contains API_ID"
    else
        log_warning ".env file may not contain required API_ID"
    fi
    
    if grep -q "API_HASH" "config/.env"; then
        log_info ".env file contains API_HASH"
    else
        log_warning ".env file may not contain required API_HASH"
    fi
else
    log_warning "No .env file found. Bot will likely fail to start."
fi

# Start the bot with verbose output
log_info "Starting Telegram bot with nohup using $PYTHON_CMD..."
log_info "Full command: $PYTHON_CMD $(pwd)/src/userbot/userbot_tg.py"
log_info "Running initial test to check for immediate errors..."

# Test run the bot briefly to catch immediate errors
$PYTHON_CMD -c "
import sys
try:
    sys.path.append('$(pwd)')
    import src.userbot.userbot_tg
    print('✅ Bot module imports successfully')
except Exception as e:
    print('❌ Error importing bot module: ' + str(e))
    sys.exit(1)
" || {
    log_error "Bot failed initial import test. See error above."
    exit 1
}

# Start the bot for real
nohup $PYTHON_CMD $(pwd)/src/userbot/userbot_tg.py > logs/bot_output.log 2>&1 &
BOT_PID=$!

# Verify the bot started properly
log_info "Waiting 5 seconds to verify bot startup..."
sleep 5
if ps -p $BOT_PID > /dev/null; then
    log_info "Bot started successfully with PID: $BOT_PID"
else
    log_error "Bot failed to start or crashed immediately"
    log_info "Last 20 lines of bot_output.log:"
    tail -n 20 logs/bot_output.log
    
    # Try to collect more diagnostic information
    log_info "Checking for Python errors..."
    grep -i "error" logs/bot_output.log
    grep -i "exception" logs/bot_output.log
    
    log_info "Starting monitor anyway to attempt recovery..."
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
EOF

chmod +x ${PROJECT_ROOT}/scripts/check_status.sh

# Verify both processes started
echo ""
echo "========================================================="
if ps -p $BOT_PID > /dev/null; then
    log_info "Bot started successfully with PID: $BOT_PID"
else
    log_error "Failed to start bot - check logs for details"
    log_info "The monitor script will attempt to restart it automatically"
fi

if ps -p $MONITOR_PID > /dev/null; then
    log_info "Monitor started successfully with PID: $MONITOR_PID"
else
    log_error "Failed to start monitor"
fi

echo ""
log_info "To check status: bash scripts/check_status.sh"
log_info "To view bot logs: cat logs/bot_output.log"
log_info "To view monitor logs: cat logs/monitor.log"
log_info "To view debug info: cat logs/debug.log"
log_info "To stop the bot: pkill -f \"python.*userbot_tg.py\" "
log_info "To stop everything: pkill -f \"python.*userbot_tg.py\"; pkill -f \"monitor_bot.sh\" "
echo "========================================================="