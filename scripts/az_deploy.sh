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
    
    # Create target directory on VM if it doesn't exist
    ssh -i "$SSH_KEY_PATH" "$AZURE_VM_USER@$AZURE_VM_IP" "
        if [ ! -d \"$AZURE_DEPLOY_DIR\" ]; then
            sudo mkdir -p \"$AZURE_DEPLOY_DIR\"
            sudo chown -R $AZURE_VM_USER:$AZURE_VM_USER \"$AZURE_DEPLOY_DIR\"
            sudo chmod -R 755 \"$AZURE_DEPLOY_DIR\"
        fi
    " || {
        echo "Failed to create target directory on VM"
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
        # Set permissions
        sudo chown -R $AZURE_VM_USER:$AZURE_VM_USER \"$AZURE_DEPLOY_DIR\"
        sudo chmod -R 755 \"$AZURE_DEPLOY_DIR\"
        
        # Verify files were transferred
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
    
    # Get NSG associated with the network interface
    local nsg_id=$(az network nic show \
        --ids "$nic_id" \
        --query "networkSecurityGroup.id" \
        --output tsv)
    
    if [ -z "$nsg_id" ]; then
        echo "No NSG associated with VM. Creating default NSG..."
        
        # Create a default NSG
        local nsg_name="${AZURE_VM_NAME}-nsg"
        az network nsg create \
            --resource-group $AZURE_RESOURCE_GROUP \
            --name $nsg_name \
            --subscription $AZURE_SUBSCRIPTION_ID
        
        # Add SSH rule
        az network nsg rule create \
            --resource-group $AZURE_RESOURCE_GROUP \
            --nsg-name $nsg_name \
            --name AllowSSH \
            --priority 1000 \
            --direction Inbound \
            --access Allow \
            --protocol Tcp \
            --source-port-ranges '*' \
            --destination-port-ranges 22 \
            --subscription $AZURE_SUBSCRIPTION_ID
        
        # Associate NSG with NIC
        az network nic update \
            --ids "$nic_id" \
            --network-security-group $nsg_name \
            --subscription $AZURE_SUBSCRIPTION_ID
    else
        # Get NSG name and resource group
        local nsg_name=$(az network nsg show \
            --ids "$nsg_id" \
            --query "name" \
            --output tsv)
        
        local nsg_rg=$(az network nsg show \
            --ids "$nsg_id" \
            --query "resourceGroup" \
            --output tsv)
        
        # Check if SSH port is open
        local ssh_rule=$(az network nsg rule list \
            --resource-group "$nsg_rg" \
            --nsg-name "$nsg_name" \
            --query "[?destinationPortRanges[0]=='22'].name" \
            --output tsv)
        
        if [ -z "$ssh_rule" ]; then
            echo "SSH port not open. Adding SSH rule..."
            
            # Add SSH rule
            az network nsg rule create \
                --resource-group "$nsg_rg" \
                --nsg-name "$nsg_name" \
                --name AllowSSH \
                --priority 1000 \
                --direction Inbound \
                --access Allow \
                --protocol Tcp \
                --source-port-ranges '*' \
                --destination-port-ranges 22 \
                --subscription $AZURE_SUBSCRIPTION_ID
        fi
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

# Function to deploy the application
deploy_application() {
    echo "Starting deployment process..."
    
    # Check Azure login and VM status
    check_azure_login || return 1
    check_vm_status || return 1
    
    # Get Azure region
    AZURE_REGION=$(az vm show \
        --resource-group $AZURE_RESOURCE_GROUP \
        --name $AZURE_VM_NAME \
        --query "location" \
        --output tsv)
    
    echo "Azure Region: $AZURE_REGION"
    
    # Transfer files to VM
    transfer_files || return 1
    
    # Update system packages
    execute_remote_command "
        sudo apt-get update
        sudo apt-get upgrade -y
    " || return 1
    
    # Install required packages
    execute_remote_command "
        sudo apt-get install -y python3 python3-pip python3-venv git
    " || return 1
    
    # Set up Python virtual environment and install dependencies
    execute_remote_command "
        # Create virtual environment
        cd $AZURE_DEPLOY_DIR
        python3 -m venv venv
        
        # Activate virtual environment and install dependencies
        . venv/bin/activate && \
        pip install --upgrade pip && \
        if [ -f \"requirements.txt\" ]; then
            pip install -r requirements.txt
        else
            echo \"Error: requirements.txt not found\"
    exit 1
        fi
    " || return 1
    
    # Set up environment variables
    execute_remote_command "
        # Create config directory if it doesn't exist
        if [ ! -d \"$AZURE_DEPLOY_DIR/config\" ]; then
            mkdir -p $AZURE_DEPLOY_DIR/config
        fi
        
        # Update .env file with Azure region
        if [ -f \"$AZURE_DEPLOY_DIR/config/.env\" ]; then
            # Remove existing AZURE_REGION if present
            sed -i '/^AZURE_REGION=/d' $AZURE_DEPLOY_DIR/config/.env
            sed -i '/^AZURE_LOCATION=/d' $AZURE_DEPLOY_DIR/config/.env
        fi
        
        # Add Azure region to .env file
        echo \"AZURE_REGION=$AZURE_REGION\" >> $AZURE_DEPLOY_DIR/config/.env
        echo \"AZURE_LOCATION=$AZURE_REGION\" >> $AZURE_DEPLOY_DIR/config/.env
        
        # Set permissions
        sudo chown -R $AZURE_VM_USER:$AZURE_VM_USER $AZURE_DEPLOY_DIR
        sudo chmod -R 755 $AZURE_DEPLOY_DIR
        if [ -f \"$AZURE_DEPLOY_DIR/config/.env\" ]; then
            sudo chmod 600 $AZURE_DEPLOY_DIR/config/.env
        fi
        
        # Export environment variables
        export AZURE_REGION=$AZURE_REGION
        export AZURE_LOCATION=$AZURE_REGION
    " || return 1
    
    # Set up systemd service
    execute_remote_command "
        # Create systemd service file
        sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null << EOF
[Unit]
Description=Telegram Bot Service
After=network.target

[Service]
Type=simple
User=$AZURE_VM_USER
WorkingDirectory=/home/$AZURE_VM_USER/
Environment=\"PATH=$AZURE_DEPLOY_DIR/venv/bin:\$PATH\"
ExecStart=/bin/bash $AZURE_DEPLOY_DIR/scripts/run_bot.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

        # Make run_bot.sh executable
        chmod +x $AZURE_DEPLOY_DIR/scripts/run_bot.sh
        
        # Reload systemd and enable service
        sudo systemctl daemon-reload
        sudo systemctl enable $SERVICE_NAME
        sudo systemctl start $SERVICE_NAME
    " || return 1
    
    echo "Deployment completed successfully!"
    return 0
}

# Function to check deployment status
check_deployment() {
    echo "Checking deployment status..."
    
    # Check if SSH key exists
    if [ ! -f "$SSH_KEY_PATH" ]; then
        echo "Error: SSH key not found at $SSH_KEY_PATH"
        return 1
    fi
    
    # Set correct permissions for SSH key
    chmod 600 "$SSH_KEY_PATH"
    
    ssh -i "$SSH_KEY_PATH" "$AZURE_VM_USER@$AZURE_VM_IP" "
        systemctl status $SERVICE_NAME
    "
}

# Function to view logs
view_logs() {
    echo "Viewing bot logs..."
    
    # Check if SSH key exists
    if [ ! -f "$SSH_KEY_PATH" ]; then
        echo "Error: SSH key not found at $SSH_KEY_PATH"
        return 1
    fi
    
    # Set correct permissions for SSH key
    chmod 600 "$SSH_KEY_PATH"
    
    # View logs using sudo
    ssh -i "$SSH_KEY_PATH" "$AZURE_VM_USER@$AZURE_VM_IP" "
        # Make sure monitor_bot.sh is executable
        sudo chmod +x $AZURE_DEPLOY_DIR/scripts/monitor_bot.sh
        
        # Check if monitor_bot.sh exists
        if [ ! -f \"$AZURE_DEPLOY_DIR/scripts/monitor_bot.sh\" ]; then
            echo '❌ monitor_bot.sh not found'
            exit 1
        fi
        
        # Create logs directory if it doesn't exist
        sudo mkdir -p $AZURE_DEPLOY_DIR/logs
        
        # Set correct permissions for logs directory
        sudo chown -R $AZURE_VM_USER:$AZURE_VM_USER $AZURE_DEPLOY_DIR/logs
        sudo chmod -R 755 $AZURE_DEPLOY_DIR/logs
        
        # Start monitor_bot.sh in the background with sudo
        echo 'Starting log monitor...'
        cd $AZURE_DEPLOY_DIR
        sudo -u $AZURE_VM_USER nohup ./scripts/monitor_bot.sh > logs/monitor_output.log 2>&1 &
        MONITOR_PID=\$!
        
        # Wait a moment for monitor to start
        sleep 2
        
        # Check if monitor is running
        if ps -p \$MONITOR_PID > /dev/null; then
            echo '✅ Log monitor started successfully'
            echo 'Monitoring logs... (Press Ctrl+C to stop)'
            
            # Tail the monitor output with sudo
            sudo tail -f logs/monitor_output.log
        else
            echo '❌ Failed to start log monitor'
            echo 'Last 20 lines of monitor_output.log:'
            sudo tail -n 20 logs/monitor_output.log
            
            # Try alternative method using journalctl
            echo 'Trying alternative method using journalctl...'
            sudo journalctl -u $SERVICE_NAME -f
        fi
    " || {
        echo "Failed to view bot logs"
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
    
    # Restart the bot using sudo
    ssh -i "$SSH_KEY_PATH" "$AZURE_VM_USER@$AZURE_VM_IP" "
        # Make sure scripts are executable
        sudo chmod +x $AZURE_DEPLOY_DIR/scripts/stop_bot.sh
        sudo chmod +x $AZURE_DEPLOY_DIR/scripts/run_bot.sh
        
        # First stop the bot using sudo
        echo 'Stopping bot...'
        cd $AZURE_DEPLOY_DIR
        if sudo ./scripts/stop_bot.sh; then
            echo '✅ Bot stopped successfully'
            
            # Wait a moment
            sleep 2
            
            # Then start the bot using sudo
            echo 'Starting bot...'
            if sudo ./scripts/run_bot.sh; then
                echo '✅ Bot started successfully'
                exit 0
            else
                echo '❌ Failed to start bot'
                echo 'Last 20 lines of bot_output.log:'
                sudo tail -n 20 logs/bot_output.log
                exit 1
            fi
        else
            echo '❌ Failed to stop bot'
            echo 'Trying alternative stop method...'
            
            # Try to stop using systemctl
            if sudo systemctl stop $SERVICE_NAME; then
                echo '✅ Bot stopped using systemctl'
                sleep 2
                
                # Start using systemctl
                if sudo systemctl start $SERVICE_NAME; then
                    echo '✅ Bot started using systemctl'
                    exit 0
                else
                    echo '❌ Failed to start bot using systemctl'
                    sudo systemctl status $SERVICE_NAME
                    exit 1
                fi
            else
                echo '❌ Failed to stop bot using systemctl'
                exit 1
            fi
        fi
    " || {
        echo "Failed to restart bot service"
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
    
    # Stop the bot with sudo
    ssh -i "$SSH_KEY_PATH" "$AZURE_VM_USER@$AZURE_VM_IP" "
        # First try to stop using systemd
        if sudo systemctl is-active $SERVICE_NAME > /dev/null 2>&1; then
            echo 'Stopping bot service...'
            sudo systemctl stop $SERVICE_NAME
            sleep 2
        fi
        
        # Then check for any remaining processes
        if ps aux | grep -v grep | grep -q \"python.*main.py\"; then
            echo 'Found running bot process. Stopping it...'
            
            # Get the process IDs
            PIDS=\$(ps aux | grep \"python.*main.py\" | grep -v grep | awk '{print \$2}')
            
            # Try to stop each process with sudo
            for PID in \$PIDS; do
                echo \"Stopping process \$PID...\"
                if sudo kill \$PID 2>/dev/null; then
                    echo \"Successfully stopped process \$PID\"
                else
                    echo \"Failed to stop process \$PID with kill, trying kill -9...\"
                    if sudo kill -9 \$PID 2>/dev/null; then
                        echo \"Successfully force stopped process \$PID\"
                    else
                        echo \"Failed to force stop process \$PID\"
                    fi
                fi
            done
            
            # Wait a moment and check if processes are still running
            sleep 2
            if ps aux | grep -v grep | grep -q \"python.*main.py\"; then
                echo '❌ Some bot processes are still running'
                exit 1
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

# Function to start the bot
start_bot() {
    echo "Starting bot service..."
    
    # Check if SSH key exists
    if [ ! -f "$SSH_KEY_PATH" ]; then
        echo "Error: SSH key not found at $SSH_KEY_PATH"
        return 1
    fi
    
    # Set correct permissions for SSH key
    chmod 600 "$SSH_KEY_PATH"
    
    # Start the service with proper error handling
    local ssh_output
    ssh_output=$(ssh -i "$SSH_KEY_PATH" "$AZURE_VM_USER@$AZURE_VM_IP" "
        # Make sure run_bot.sh is executable
        sudo chmod +x $AZURE_DEPLOY_DIR/scripts/run_bot.sh
        
        # Check if bot is already running
        if systemctl is-active $SERVICE_NAME > /dev/null 2>&1; then
            echo '✅ Bot service is already running'
            systemctl status $SERVICE_NAME
            exit 0
        fi
        
        # Start the bot service
        echo 'Starting bot service...'
        sudo systemctl start $SERVICE_NAME
        
        # Wait for service to start
        sleep 5
        
        # Check service status
        if systemctl is-active $SERVICE_NAME > /dev/null 2>&1; then
            echo '✅ Bot service started successfully'
            systemctl status $SERVICE_NAME
            exit 0
        else
            echo '❌ Failed to start bot service'
            echo 'Service status:'
            systemctl status $SERVICE_NAME
            echo 'Last 20 lines of bot_output.log:'
            sudo tail -n 20 $AZURE_DEPLOY_DIR/logs/bot_output.log
            exit 1
        fi
    ")
    
    local ssh_exit_code=$?
    
    # Check if service is actually running
    if ssh -i "$SSH_KEY_PATH" "$AZURE_VM_USER@$AZURE_VM_IP" "systemctl is-active $SERVICE_NAME > /dev/null 2>&1"; then
        echo "✅ Bot service is running"
        ssh -i "$SSH_KEY_PATH" "$AZURE_VM_USER@$AZURE_VM_IP" "systemctl status $SERVICE_NAME"
        return 0
    fi
    
    # If we get here, the service is not running
    echo "Failed to start bot service"
    echo "SSH output:"
    echo "$ssh_output"
    return 1
}

# Function to update the bot
update_bot() {
    echo "Updating bot..."
    transfer_files || return 1
    
    execute_remote_command "
        cd $AZURE_DEPLOY_DIR
        
        # Activate virtual environment and update dependencies
        . venv/bin/activate && \
        pip install --upgrade pip && \
        if [ -f \"requirements.txt\" ]; then
            pip install -r requirements.txt
        else
            echo \"Error: requirements.txt not found\"
            exit 1
        fi
        
        # Restart the service
        sudo systemctl restart $SERVICE_NAME
    " || return 1
    
    echo "Bot updated successfully!"
    return 0
}

# Function to check bot status
check_status() {
    echo "Checking bot status..."
    
    # Check if SSH key exists
    if [ ! -f "$SSH_KEY_PATH" ]; then
        echo "Error: SSH key not found at $SSH_KEY_PATH"
        return 1
    fi
    
    # Set correct permissions for SSH key
    chmod 600 "$SSH_KEY_PATH"
    
    # Check status using check_status.sh with sudo
    ssh -i "$SSH_KEY_PATH" "$AZURE_VM_USER@$AZURE_VM_IP" "
        # Make sure check_status.sh is executable
        sudo chmod +x $AZURE_DEPLOY_DIR/scripts/check_status.sh
        
        # Check if check_status.sh exists
        if [ ! -f \"$AZURE_DEPLOY_DIR/scripts/check_status.sh\" ]; then
            echo '❌ check_status.sh not found'
            exit 1
        fi
        
        # Run check_status.sh with sudo
        echo 'Running status check...'
        cd $AZURE_DEPLOY_DIR
        sudo ./scripts/check_status.sh
        
        # Also check systemd service status
        echo ''
        echo '=== Systemd Service Status ==='
        sudo systemctl status $SERVICE_NAME
        
        # Check process status
        echo ''
        echo '=== Process Status ==='
        sudo ps aux | grep -v grep | grep \"python.*main.py\"
        
        # Check logs
        echo ''
        echo '=== Latest Logs ==='
        sudo tail -n 20 logs/bot_output.log 2>/dev/null || echo 'No logs found'
    " || {
        echo "Failed to check bot status"
        return 1
    }
    
    return 0
}

# Main menu
show_menu() {
    echo "Azure Bot Deployment Menu"
    echo "1. Connect to VM"
    echo "2. Deploy Application"
    echo "3. Check Deployment Status"
    echo "4. View Logs"
    echo "5. Start Bot"
    echo "6. Stop Bot"
    echo "7. Update Bot"
    echo "8. Check Bot Status"
    echo "9. Exit"
    echo -n "Enter your choice: "
}

# Handle user input
while true; do
    show_menu
    read choice
    case $choice in
        1) connect_to_vm ;;
        2) deploy_application ;;
        3) check_deployment ;;
        4) view_logs ;;
        5) restart_bot ;;
        6) stop_bot ;;
        7) update_bot ;;
        8) check_status ;;
        9) echo "Exiting..."; exit 0 ;;
        *) echo "Invalid choice. Please try again." ;;
    esac
done