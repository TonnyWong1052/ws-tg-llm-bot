#!/bin/bash

# Monitor script for Telegram bot on Azure VM
# This script monitors the bot service and restarts it if needed

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load environment variables
if [ -f "$PROJECT_ROOT/config/.env" ]; then
    export $(cat "$PROJECT_ROOT/config/.env" | grep -v '^#' | xargs)
else
    echo "Error: $PROJECT_ROOT/config/.env file not found"
    exit 1
fi

# Create log directory if it doesn't exist
sudo mkdir -p $LOG_DIR
sudo chown azureuser:azureuser $LOG_DIR

# Function to log messages
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S'): $1" | tee -a $LOG_DIR/monitor.log
}

# Function to execute remote command
execute_remote_command() {
    local command="$1"
    az vm run-command invoke \
        --resource-group $AZURE_RESOURCE_GROUP \
        --name $AZURE_VM_NAME \
        --subscription $AZURE_SUBSCRIPTION_ID \
        --command-id RunShellScript \
        --scripts "$command"
}

# Function to check service status
check_service() {
    execute_remote_command "systemctl is-active $SERVICE_NAME" | grep -q "active"
}

# Function to restart service
restart_service() {
    log_message "Restarting $SERVICE_NAME service..."
    execute_remote_command "sudo systemctl restart $SERVICE_NAME"
}

# Function to collect debug info
collect_debug_info() {
    log_message "Collecting debug information..."
    execute_remote_command "
        echo '=== System Information ===' > $LOG_DIR/debug.log
        uname -a >> $LOG_DIR/debug.log
        echo '\n=== Disk Space ===' >> $LOG_DIR/debug.log
        df -h >> $LOG_DIR/debug.log
        echo '\n=== Memory Usage ===' >> $LOG_DIR/debug.log
        free -m >> $LOG_DIR/debug.log
        echo '\n=== Service Status ===' >> $LOG_DIR/debug.log
        systemctl status $SERVICE_NAME >> $LOG_DIR/debug.log
        echo '\n=== Recent Logs ===' >> $LOG_DIR/debug.log
        journalctl -u $SERVICE_NAME -n 50 >> $LOG_DIR/debug.log
    "
}

# Main monitoring loop
while true; do
    if ! check_service; then
        log_message "Service $SERVICE_NAME is not running. Attempting to restart..."
        collect_debug_info
        restart_service
        
        # Wait and check if restart was successful
        sleep 10
        if ! check_service; then
            log_message "Failed to restart $SERVICE_NAME. Please check the logs."
        else
            log_message "Successfully restarted $SERVICE_NAME."
        fi
    else
        log_message "Service $SERVICE_NAME is running normally."
    fi
    
    # Wait before next check
    sleep 60
done

if [ ! -d \"$AZURE_DEPLOY_DIR\" ]; then
    sudo mkdir -p \"$AZURE_DEPLOY_DIR\"
    sudo chown -R $AZURE_VM_USER:$AZURE_VM_USER \"$AZURE_DEPLOY_DIR\"
    sudo chmod -R 755 \"$AZURE_DEPLOY_DIR\"
fi

scp -i "$SSH_KEY_PATH" -r "$PROJECT_ROOT"/* "$AZURE_VM_USER@$AZURE_VM_IP:$AZURE_DEPLOY_DIR/"
