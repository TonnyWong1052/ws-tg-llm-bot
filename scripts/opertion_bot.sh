#!/bin/bash

# This script is designed to run locally to monitor and restart the bot if needed
# For Azure deployment, use az_deploy.sh instead

# Navigate to the project root directory
cd "$(dirname "$0")/.." || exit
PROJECT_ROOT=$(pwd)

# Use local logs directory
LOG_DIR="$(pwd)/logs"
echo "Running locally, using $LOG_DIR for logs"

# Ensure log directory exists and has correct permissions
mkdir -p "$LOG_DIR"
chmod -R 777 "$LOG_DIR" 2>/dev/null || true

# Define logging functions
log_info() {
    echo "[$(date)] INFO: $1" >> "$LOG_DIR/bot_check.log"
    echo -e "\033[0;32m[INFO]\033[0m $1"
}

log_error() {
    echo "[$(date)] ERROR: $1" >> "$LOG_DIR/bot_check.log"
    echo -e "\033[0;31m[ERROR]\033[0m $1" >&2
}

# Function to check if bot is running
check_bot_status() {
    if pgrep -f "python.*main.py" > /dev/null; then
        return 0  # Bot is running
    else
        return 1  # Bot is not running
    fi
}

# Function to check if monitor bot is running
check_monitor_status() {
    if pgrep -f "opertion_bot.sh" > /dev/null; then
        return 0  # Monitor is running
    else
        return 1  # Monitor is not running
    fi
}

# Function to restart the bot
restart_bot() {
    log_info "Attempting to restart the bot..."
    
    # First, try to stop any existing bot processes
    if pgrep -f "python.*main.py" > /dev/null; then
        log_info "Found existing bot process. Stopping it..."
        pkill -f "python.*main.py"
        sleep 5
    fi
    
    # Start the bot using run_bot.sh
    if [ -f "$PROJECT_ROOT/scripts/run_bot.sh" ]; then
        log_info "Starting bot using run_bot.sh..."
        bash "$PROJECT_ROOT/scripts/run_bot.sh" > "$LOG_DIR/bot_restart.log" 2>&1 &
        RESTART_PID=$!
        
        # Wait a moment and check if the restart was successful
        sleep 10
        if check_bot_status; then
            log_info "Bot restarted successfully with PID: $(pgrep -f 'python.*main.py')"
            return 0
        else
            log_error "Failed to restart bot. Check $LOG_DIR/bot_restart.log for details"
            return 1
        fi
    else
        log_error "run_bot.sh not found at $PROJECT_ROOT/scripts/run_bot.sh"
        return 1
    fi
}

# Function to stop the monitor bot
stop_monitor() {
    log_info "Stopping monitor bot..."
    
    # Find and kill the monitor process
    if pgrep -f "opertion_bot.sh" > /dev/null; then
        pkill -f "opertion_bot.sh"
        sleep 2
        if ! check_monitor_status; then
            log_info "Monitor bot stopped successfully"
            return 0
        else
            log_error "Failed to stop monitor bot"
            return 1
        fi
    else
        log_info "Monitor bot is not running"
        return 0
    fi
}

# Handle command line arguments
case "$1" in
    start)
        # Start the monitor in background
        if check_monitor_status; then
            log_info "Monitor bot is already running"
            exit 0
        else
            log_info "Starting monitor bot in background..."
            nohup "$0" monitor > "$LOG_DIR/monitor.log" 2>&1 &
            MONITOR_PID=$!
            echo "Monitor bot started with PID: $MONITOR_PID"
            exit 0
        fi
        ;;
    stop)
        # Stop the monitor
        stop_monitor
        exit $?
        ;;
    status)
        # Check monitor status
        if check_monitor_status; then
            echo "Monitor bot is running"
            exit 0
        else
            echo "Monitor bot is not running"
            exit 1
        fi
        ;;
    monitor)
        # Main monitoring loop
        log_info "Starting local bot monitoring service..."
        
        while true; do
            if ! check_bot_status; then
                log_error "Bot is not running! Attempting to restart..."
                if restart_bot; then
                    log_info "Bot restart successful"
                else
                    log_error "Bot restart failed. Will try again in 1 minutes."
                fi
            else
                log_info "Bot is running normally"
            fi
            
            # Wait for 1 minutes before next check
            sleep 60
        done
        ;;
    *)
        echo "Usage: $0 {start|stop|status}"
        echo "  start  - Start the monitor bot in background"
        echo "  stop   - Stop the monitor bot"
        echo "  status - Check if the monitor bot is running"
        exit 1
        ;;
esac 