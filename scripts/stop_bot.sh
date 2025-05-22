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
    echo "$(date): INFO - $message" >> logs/bot_stop.log
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

# Function to stop a process
stop_process() {
    local pattern=$1
    local process_name=$2
    local force_stop=$3
    
    if check_process "$pattern"; then
        log_info "Found running $process_name process. Stopping it with elevated privileges..."
        
        if [ "$force_stop" = true ]; then
            sudo pkill -9 -f "$pattern"
        else
            sudo pkill -f "$pattern"
        fi
        
        # Wait for process to stop
        local max_wait=10
        local wait_time=0
        while check_process "$pattern" && [ $wait_time -lt $max_wait ]; do
            sleep 1
            wait_time=$((wait_time + 1))
        done
        
        if ! check_process "$pattern"; then
            log_info "✅ $process_name stopped successfully"
            return 0
        else
            log_error "Failed to stop $process_name process"
            return 1
        fi
    else
        log_info "No $process_name process found"
        return 0
    fi
}

echo "Stopping Telegram bot..."

# Stop bot process
if ! stop_process "python.*main.py" "bot" false; then
    log_info "Trying force stop for bot..."
    if ! stop_process "python.*main.py" "bot" true; then
        log_error "Failed to force stop bot process"
        exit 1
    fi
fi

# Stop monitor process
if ! stop_process "monitor_bot.sh" "monitor" false; then
    log_info "Trying force stop for monitor..."
    if ! stop_process "monitor_bot.sh" "monitor" true; then
        log_error "Failed to force stop monitor process"
        exit 1
    fi
fi

# Verify all processes are stopped
if check_process "python.*main.py" || check_process "monitor_bot.sh"; then
    log_error "Some processes are still running after stop attempts"
    exit 1
fi

log_info "All processes have been stopped successfully"
exit 0