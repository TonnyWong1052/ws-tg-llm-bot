#!/bin/bash

# Azure deployment script for Telegram bot
# This script handles deployment to Azure VM

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

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check for required tools
if ! command_exists az; then
    echo "Azure CLI is not installed. Please install it first."
    exit 1
fi

if ! command_exists scp; then
    echo "SCP is not installed. Please install it first."
    exit 1
fi

# Function to get VM IP address
get_vm_ip() {
    az vm show \
        --resource-group $AZURE_RESOURCE_GROUP \
        --name $AZURE_VM_NAME \
        --show-details \
        --query "publicIps" \
        --output tsv
}

# Function to prepare files for transfer
prepare_files() {
    echo "Preparing files for transfer..."
    
    # Check if .env exists, if not create it
    if [ ! -f "$PROJECT_ROOT/config/.env" ]; then
        echo "Creating .env file..."
        cat > "$PROJECT_ROOT/config/.env" << EOF
# Azure Configuration
AZURE_RESOURCE_GROUP="WEB-BOT_GROUP"
AZURE_VM_NAME="web-bot"
AZURE_SUBSCRIPTION_ID="your_subscription_id"
AZURE_DEPLOY_DIR="/home/23030897d/ws-tg-llm-bot"
AZURE_GIT_REPO="https://github.com/yourusername/ws-tg-llm-bot.git"

# Service Configuration
SERVICE_NAME="tg-bot"
LOG_DIR="/var/log/tg-bot"

# Bot Configuration
BOT_TOKEN="your_bot_token"
API_ID="your_api_id"
API_HASH="your_api_hash"
SESSION_NAME="session_name"
EOF
    fi
    
    # Check if requirements.txt exists, if not create it
    if [ ! -f "$PROJECT_ROOT/requirements.txt" ]; then
        echo "Creating requirements.txt file..."
        cat > "$PROJECT_ROOT/requirements.txt" << EOF
telethon==1.31.1
python-dotenv==1.0.0
requests==2.31.0
EOF
    fi
    
    # Check if src directory exists
    if [ ! -d "$PROJECT_ROOT/src" ]; then
        echo "Error: src directory not found"
        return 1
    fi
    
    # Check if scripts directory exists
    if [ ! -d "$PROJECT_ROOT/scripts" ]; then
        echo "Error: scripts directory not found"
        return 1
    fi
    
    return 0
}

# Function to execute remote command
execute_remote_command() {
    local command=$1
    
    echo "Executing remote command..."
    # Use az vm run-command instead of az ssh vm for command execution
    az vm run-command invoke \
        --resource-group $AZURE_RESOURCE_GROUP \
        --name $AZURE_VM_NAME \
        --subscription $AZURE_SUBSCRIPTION_ID \
        --command-id RunShellScript \
        --scripts "$command" || {
        echo "Failed to execute remote command"
        return 1
    }
    
    return 0
}

# Function to setup SSH key
setup_ssh_key() {
    echo "Setting up SSH connection..."
    
    # Create SSH config file
    mkdir -p ~/.ssh
    cat > ~/.ssh/config << EOF
Host $AZURE_VM_NAME
    HostName $(get_vm_ip)
    User 23030897d
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
EOF
    
    # Test SSH connection
    echo "Testing SSH connection..."
    ssh $AZURE_VM_NAME "echo 'SSH connection successful'" || {
        echo "Failed to establish SSH connection"
        return 1
    }
    
    echo "SSH connection established successfully"
    return 0
}

# Function to transfer files to VM
transfer_files() {
    echo "Transferring files to VM..."
    
    # Prepare files first
    prepare_files || return 1
    
    # Check if SSH key exists
    if [ ! -f "$SSH_KEY_PATH" ]; then
        echo "Error: SSH key not found at $SSH_KEY_PATH"
        return 1
    fi
    
    # Set correct permissions for SSH key
    chmod 600 "$SSH_KEY_PATH"
    
    # 先在 VM 上建立所有必要目錄
    ssh -i "$SSH_KEY_PATH" "$AZURE_VM_USER@$AZURE_VM_IP" "
        sudo mkdir -p \"$AZURE_DEPLOY_DIR/scripts\"
        sudo mkdir -p \"$AZURE_DEPLOY_DIR/src\"
        sudo mkdir -p \"$AZURE_DEPLOY_DIR/config\"
        sudo mkdir -p \"$AZURE_DEPLOY_DIR/logs\"
        sudo chown -R $AZURE_VM_USER:$AZURE_VM_USER \"$AZURE_DEPLOY_DIR\"
        sudo chmod -R 775 \"$AZURE_DEPLOY_DIR\"
    " || {
        echo "Failed to create target directories on VM"
        return 1
    }
    
    # Transfer files using scp with SSH key
    echo "Transferring files to VM..."
    scp -i "$SSH_KEY_PATH" -r "$PROJECT_ROOT"/* "$AZURE_VM_USER@$AZURE_VM_IP:$AZURE_DEPLOY_DIR/" || {
        echo "Failed to transfer files to VM"
        return 1
    }
    
    # Set correct permissions on VM
    ssh -i "$SSH_KEY_PATH" "$AZURE_VM_USER@$AZURE_VM_IP" "
        sudo chown -R $AZURE_VM_USER:$AZURE_VM_USER \"$AZURE_DEPLOY_DIR\"
        sudo chmod -R 775 \"$AZURE_DEPLOY_DIR\"
        sudo mkdir -p \"/home/azureuser/logs\"
        sudo chown -R $AZURE_VM_USER:$AZURE_VM_USER \"/home/azureuser/logs\"
        sudo chmod -R 777 \"/home/azureuser/logs\"
        sudo find \"$AZURE_DEPLOY_DIR/scripts\" -type f -name \"*.sh\" -exec chmod +x {} \;
        if [ -f \"$AZURE_DEPLOY_DIR/config/.env\" ]; then
            sudo chmod 600 \"$AZURE_DEPLOY_DIR/config/.env\"
        fi
        if [ ! -d \"$AZURE_DEPLOY_DIR/src\" ] || [ ! -d \"$AZURE_DEPLOY_DIR/scripts\" ]; then
            echo 'Error: Files were not transferred correctly'
            exit 1
        fi
        echo 'Files transferred successfully'
    " || {
        echo "Failed to set permissions on VM"
        return 1
    }
    
    return 0
}

# Function to wait for any running commands to complete
wait_for_running_commands() {
    local max_attempts=10
    local attempt=1
    local wait_time=15
    
    while [ $attempt -le $max_attempts ]; do
        echo "Checking for running commands (attempt $attempt/$max_attempts)..."
        
        # Check if any run commands are in progress
        local status=$(az vm run-command list \
            --resource-group $AZURE_RESOURCE_GROUP \
            --vm-name $AZURE_VM_NAME \
            --subscription $AZURE_SUBSCRIPTION_ID \
            --query "[?provisioningState=='Running']" \
            --output tsv 2>/dev/null)
        
        if [ -z "$status" ]; then
            echo "No commands running, proceeding..."
            return 0
        fi
        
        echo "Command still running, waiting $wait_time seconds..."
        sleep $wait_time
        attempt=$((attempt + 1))
    done
    
    echo "Warning: Timeout waiting for commands to complete. Proceeding anyway..."
    return 0
}

# Function to connect to Azure VM
connect_to_vm() {
    echo "Connecting to Azure VM..."
    
    # Check if SSH key exists
    if [ ! -f "$SSH_KEY_PATH" ]; then
        echo "Error: SSH key not found at $SSH_KEY_PATH"
        return 1
    fi
    
    # Set correct permissions for SSH key
    chmod 600 "$SSH_KEY_PATH"
    
    # Connect using SSH with key
    ssh -i "$SSH_KEY_PATH" "$AZURE_VM_USER@$AZURE_VM_IP"
}

# Function to check Azure CLI login status
check_azure_login() {
    echo "Checking Azure CLI login status..."
    
    # Check if Azure CLI is installed
    if ! command_exists az; then
        echo "Azure CLI is not installed. Please install it first."
        return 1
    fi
    
    # Check if logged in
    if ! az account show &>/dev/null; then
        echo "Azure CLI not logged in. Please login first."
        az login
        if [ $? -ne 0 ]; then
            echo "Failed to login to Azure CLI"
            return 1
        fi
    fi
    
    # Check if subscription is set
    if [ -z "$AZURE_SUBSCRIPTION_ID" ]; then
        echo "Azure subscription ID not set. Please set it in your .env file."
        return 1
    fi
    
    # Set subscription and verify
    echo "Setting Azure subscription..."
    az account set --subscription "$AZURE_SUBSCRIPTION_ID"
    if [ $? -ne 0 ]; then
        echo "Failed to set Azure subscription"
        return 1
    fi
    
    # Verify subscription access
    echo "Verifying subscription access..."
    if ! az group list --subscription "$AZURE_SUBSCRIPTION_ID" &>/dev/null; then
        echo "No access to subscription. Please check your permissions."
        return 1
    fi
    
    return 0
}

# Function to check VM network settings
check_vm_network() {
    echo "Checking VM network settings..."
    
    # Get VM's network interface
    local nic_id=$(az vm show \
        --resource-group $AZURE_RESOURCE_GROUP \
        --name $AZURE_VM_NAME \
        --subscription $AZURE_SUBSCRIPTION_ID \
        --query "networkProfile.networkInterfaces[0].id" \
        --output tsv)
    
    if [ -z "$nic_id" ]; then
        echo "Failed to get VM's network interface"
        return 1
    fi
    
    return 0
}

# Function to check VM status
check_vm_status() {
    echo "Checking VM status..."
    
    # Check if VM exists
    if ! az vm show \
        --resource-group $AZURE_RESOURCE_GROUP \
        --name $AZURE_VM_NAME \
        --subscription $AZURE_SUBSCRIPTION_ID \
        &>/dev/null; then
        echo "VM not found. Please check your VM name and resource group."
        return 1
    fi
    
    # Check network settings
    check_vm_network || return 1
    
    # Wait for VM to be in a stable state
    local max_wait=300  # 5 minutes
    local wait_interval=30
    local total_wait=0
    
    while [ $total_wait -lt $max_wait ]; do
        # Check VM state
        local vm_status=$(az vm show \
            --resource-group $AZURE_RESOURCE_GROUP \
            --name $AZURE_VM_NAME \
            --subscription $AZURE_SUBSCRIPTION_ID \
            --query "provisioningState" \
            --output tsv 2>/dev/null)
        
        if [ $? -ne 0 ]; then
            echo "Failed to get VM status. Please check your permissions."
            return 1
        fi
        
        if [ "$vm_status" == "Succeeded" ]; then
            echo "VM is in a stable state"
            break
        elif [ "$vm_status" == "Updating" ]; then
            echo "VM is updating, waiting $wait_interval seconds... (Total wait: $total_wait seconds)"
            sleep $wait_interval
            total_wait=$((total_wait + wait_interval))
        else
            echo "VM is in an unexpected state: $vm_status"
            return 1
        fi
    done
    
    if [ $total_wait -ge $max_wait ]; then
        echo "Timeout waiting for VM to stabilize"
        return 1
    fi
    
    # Check if VM is running
    local power_state=$(az vm get-instance-view \
        --resource-group $AZURE_RESOURCE_GROUP \
        --name $AZURE_VM_NAME \
        --subscription $AZURE_SUBSCRIPTION_ID \
        --query "instanceView.statuses[?code=='PowerState/running']" \
        --output tsv)
    
    if [ -z "$power_state" ]; then
        echo "VM is not running. Starting VM..."
        az vm start \
            --resource-group $AZURE_RESOURCE_GROUP \
            --name $AZURE_VM_NAME \
            --subscription $AZURE_SUBSCRIPTION_ID
        if [ $? -ne 0 ]; then
            echo "Failed to start VM"
            return 1
        fi
        echo "Waiting for VM to start..."
        sleep 30
    fi
    
    # Check SSH service
    echo "Checking SSH service..."
    execute_remote_command "
        # Check if SSH service is installed
        if ! command -v sshd >/dev/null 2>&1; then
            echo 'SSH service not found. Installing OpenSSH...'
            sudo apt-get update
            sudo apt-get install -y openssh-server
            if [ \$? -ne 0 ]; then
                echo 'Failed to install OpenSSH'
                exit 1
            fi
        fi
        
        # Check if SSH service is running
        if ! systemctl is-active ssh >/dev/null 2>&1; then
            echo 'SSH service is not running. Starting SSH service...'
            sudo systemctl start ssh
            if [ \$? -ne 0 ]; then
                echo 'Failed to start SSH service'
                exit 1
            fi
        fi
        
        # Enable SSH service to start on boot
        sudo systemctl enable ssh
        
        echo 'SSH service is running'
    " || {
        echo "Failed to verify SSH service. Please check your VM's SSH configuration."
        return 1
    }
    
    return 0
}

# Function to stop the bot
stop_bot() {
    echo "Stopping bot service..."
    
    # Check if SSH key exists
    if [ ! -f "$SSH_KEY_PATH" ]; then
        echo "Error: SSH key not found at $SSH_KEY_PATH"
        return 1
    fi
    
    # Set correct permissions for SSH key
    chmod 600 "$SSH_KEY_PATH"
    
    # Stop the bot with elevated privileges (sudo)
    ssh -i "$SSH_KEY_PATH" "$AZURE_VM_USER@$AZURE_VM_IP" "
        # First try to stop using systemd with sudo
        if sudo systemctl is-active $SERVICE_NAME > /dev/null 2>&1; then
            echo 'Stopping bot service with sudo...'
            sudo systemctl stop $SERVICE_NAME
            sleep 3
        fi
        
        # Then check for any remaining processes and stop them with sudo
        if ps aux | grep -v grep | grep -q "python.*main.py"; then
            echo 'Found running bot processes. Stopping them with sudo...'
            
            # Get the process IDs
            PIDS=\$(ps aux | grep "python.*main.py" | grep -v grep | awk '{print \$2}')
            
            # Try to stop each process with sudo
            for PID in \$PIDS; do
                echo "Stopping process \$PID with sudo..."
                if sudo kill \$PID 2>/dev/null; then
                    echo "Successfully stopped process \$PID"
                else
                    echo "Failed to stop process \$PID with kill, trying sudo kill -9..."
                    if sudo kill -9 \$PID 2>/dev/null; then
                        echo "Successfully force stopped process \$PID with sudo"
                    else
                        echo "Failed to force stop process \$PID with sudo"
                    fi
                fi
            done
            
            # Wait a moment and check if processes are still running
            sleep 3
            if ps aux | grep -v grep | grep -q "python.*main.py"; then
                # One final attempt with full path to process and sudo pkill
                echo 'Some processes still running. Trying sudo pkill as last resort...'
                sudo pkill -9 -f "python.*main.py"
                sleep 2
                
                if ps aux | grep -v grep | grep -q "python.*main.py"; then
                    echo '❌ Some bot processes are still running after all attempts'
                    echo 'Processes:'
                    ps aux | grep -v grep | grep "python.*main.py"
                    exit 1
                else
                    echo '✅ All bot processes have been stopped with sudo pkill'
                    exit 0
                fi
            else
                echo '✅ All bot processes have been stopped'
                exit 0
            fi
        else
            echo '✅ No bot processes are running'
            exit 0
        fi
    " || {
        echo "Failed to stop bot service"
        return 1
    }
    
    return 0
}

# Function to restart the bot
restart_bot() {
    echo "Restarting bot service..."
    
    # Check if SSH key exists
    if [ ! -f "$SSH_KEY_PATH" ]; then
        echo "Error: SSH key not found at $SSH_KEY_PATH"
        return 1
    fi
    
    # Set correct permissions for SSH key
    chmod 600 "$SSH_KEY_PATH"
    
    # 先停止 bot
    stop_bot || {
        echo "Failed to stop bot before restart"
        return 1
    }
    
    # 再啟動 bot（在 VM 上執行 run_bot.sh）
    ssh -i "$SSH_KEY_PATH" "$AZURE_VM_USER@$AZURE_VM_IP" "
        cd $AZURE_DEPLOY_DIR || exit 1
        if [ -f \"$AZURE_DEPLOY_DIR/scripts/run_bot.sh\" ]; then
            echo 'Starting bot using run_bot.sh...'
            bash \"$AZURE_DEPLOY_DIR/scripts/run_bot.sh\" > /home/azureuser/logs/bot_restart.log 2>&1 &
            exit 0
        else
            echo '❌ run_bot.sh not found at $AZURE_DEPLOY_DIR/scripts/run_bot.sh'
            exit 1
        fi
    " || {
        echo "Failed to restart bot service"
        return 1
    }
    
    return 0
}

# Function to show help information
show_help() {
    echo "Azure Bot Deployment Tool - Command Help"
    echo ""
    echo "Available Commands:"
    echo "1. Connect to VM"
    echo "   - Establishes SSH connection to the Azure VM"
    echo "   - Usage: Select option 1 from the menu"
    echo ""
    echo "2. Deploy Application"
    echo "   - Deploys the bot application to Azure VM"
    echo "   - Sets up Python environment and dependencies"
    echo "   - Configures systemd service"
    echo "   - Usage: Select option 2 from the menu"
    echo ""
    echo "3. Check Deployment Status"
    echo "   - Verifies the deployment status"
    echo "   - Checks systemd service status"
    echo "   - Usage: Select option 3 from the menu"
    echo ""
    echo "4. View Logs"
    echo "   - Displays bot logs in real-time"
    echo "   - Shows last 20 lines of logs"
    echo "   - Usage: Select option 4 from the menu"
    echo ""
    echo "5. Start Bot"
    echo "   - Starts the bot service"
    echo "   - Restarts if already running"
    echo "   - Usage: Select option 5 from the menu"
    echo ""
    echo "6. Stop Bot"
    echo "   - Stops the bot service"
    echo "   - Kills all bot processes"
    echo "   - Usage: Select option 6 from the menu"
    echo ""
    echo "7. Update Bot"
    echo "   - Updates bot files and dependencies"
    echo "   - Restarts the service after update"
    echo "   - Usage: Select option 7 from the menu"
    echo ""
    echo "8. Check Bot Status"
    echo "   - Shows detailed bot status"
    echo "   - Displays process information"
    echo "   - Shows recent logs"
    echo "   - Usage: Select option 8 from the menu"
    echo ""
    echo "9. Start Operation Bot"
    echo "   - Starts the operation monitoring bot"
    echo "   - Runs in background"
    echo "   - Monitors bot status"
    echo "   - Usage: Select option 9 from the menu"
    echo ""
    echo "10. Stop Operation Bot"
    echo "    - Stops the operation monitoring bot"
    echo "    - Kills all monitoring processes"
    echo "    - Usage: Select option 10 from the menu"
    echo ""
    echo "11. Check Operation Bot Status"
    echo "    - Shows operation bot status"
    echo "    - Displays monitoring process info"
    echo "    - Shows monitoring logs"
    echo "    - Usage: Select option 11 from the menu"
    echo ""
    echo "12. Show Help"
    echo "    - Displays this help information"
    echo "    - Usage: Select option 12 from the menu"
    echo ""
    echo "13. Exit"
    echo "    - Exits the deployment tool"
    echo "    - Usage: Select option 13 from the menu"
    echo ""
    echo "Environment Variables:"
    echo "- AZURE_RESOURCE_GROUP: Azure resource group name"
    echo "- AZURE_VM_NAME: Azure VM name"
    echo "- AZURE_SUBSCRIPTION_ID: Azure subscription ID"
    echo "- AZURE_DEPLOY_DIR: Deployment directory on VM"
    echo "- AZURE_VM_USER: VM username"
    echo "- AZURE_VM_IP: VM IP address"
    echo "- SSH_KEY_PATH: Path to SSH private key"
    echo ""
    echo "Log Files:"
    echo "- /home/azureuser/logs/bot_output.log: Main bot logs"
    echo "- /home/azureuser/logs/operation_bot.log: Operation bot logs"
    echo "- /home/azureuser/logs/monitor.log: Monitoring logs"
    echo ""
    echo "Note: All commands require proper SSH key and Azure CLI configuration."
}

# Function to wait for user to press Enter
wait_for_enter() {
    echo ""
    read -p "Press Enter to return to main menu..."
    clear
}

# Main menu
show_menu() {
    echo "Azure Bot Deployment Menu"
    echo ""
    echo "Main Bot Commands:"
    echo "1. Connect to VM"
    echo "2. Deploy Application"
    echo "3. Check Deployment Status"
    echo "4. View Logs"
    echo "5. Start Bot"
    echo "6. Stop Bot"
    echo "7. Update Bot"
    echo "8. Check Bot Status"
    echo ""
    echo "Operation Bot Commands:"
    echo "   (Operation Bot is a monitoring service that watches the main bot and"
    echo "    automatically restarts it if it crashes or stops running)"
    echo "9. Start Operation Bot"
    echo "10. Stop Operation Bot"
    echo "11. Check Operation Bot Status"
    echo ""
    echo "Utility Commands:"
    echo "12. Show Help"
    echo "13. Exit"
    echo -n "Enter your choice: "
}

# Handle user input
while true; do
    show_menu
    read choice
    case $choice in
        1) 
            connect_to_vm
            wait_for_enter
            ;;
        2) 
            transfer_files
            wait_for_enter
            ;;
        3) 
            check_deployment
            wait_for_enter
            ;;
        4) 
            view_logs
            wait_for_enter
            ;;
        5) 
            restart_bot
            wait_for_enter
            ;;
        6) 
            stop_bot
            wait_for_enter
            ;;
        7) 
            update_bot
            wait_for_enter
            ;;
        8) 
            check_status
            wait_for_enter
            ;;
        9) 
            start_operation_bot
            wait_for_enter
            ;;
        10) 
            stop_operation_bot
            wait_for_enter
            ;;
        11) 
            check_operation_bot_status
            wait_for_enter
            ;;
        12) 
            show_help
            wait_for_enter
            ;;
        13) 
            echo "Exiting..."
            exit 0
            ;;
        *) 
            echo "Invalid choice. Please try again."
            wait_for_enter
            ;;
    esac
done