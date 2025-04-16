#!/bin/bash

# Setup script for Telegram Bot on Azure VM
# This script will be executed on the VM to set up and run the bot

set -e  # Exit on any error

echo "=== Setting up Telegram Bot on VM ==="

# Update package lists
echo "Updating package lists..."
sudo apt-get update

# Install required packages
echo "Installing required packages..."
sudo apt-get install -y python3-pip screen tmux

# Create project directory structure
echo "Creating project directory structure..."
BOT_DIR=~/TG-bot
mkdir -p $BOT_DIR/src/userbot
mkdir -p $BOT_DIR/src/api
mkdir -p $BOT_DIR/src/utils
mkdir -p $BOT_DIR/src/services
mkdir -p $BOT_DIR/config
mkdir -p $BOT_DIR/scripts

# Install Python dependencies
echo "Installing Python dependencies..."
cd $BOT_DIR
pip3 install --user -r requirements.txt || pip3 install --user telethon python-dotenv requests bs4

# Copy session file if it exists
if [ -f "./session_name.session" ]; then
    echo "Copying session file..."
    cp ./session_name.session $BOT_DIR/
fi

# Move .env file to config directory
if [ -f ".env" ]; then
    echo "Moving .env file to config directory..."
    cp .env $BOT_DIR/config/.env
fi

# Copy source files to appropriate directories
echo "Copying source files..."
cp -r src/* $BOT_DIR/src/
cp -r scripts/* $BOT_DIR/scripts/
cp requirements.txt $BOT_DIR/

# Make scripts executable
chmod +x $BOT_DIR/scripts/*.sh

# Set up systemd service
echo "Setting up systemd service..."
sudo bash -c "cat > /etc/systemd/system/telegram-bot.service << EOL
[Unit]
Description=Telegram Userbot Service
After=network.target

[Service]
ExecStart=/usr/bin/python3 $BOT_DIR/src/userbot/userbot_tg.py
WorkingDirectory=$BOT_DIR
Restart=always
RestartSec=10
User=${USER}
# Capture the output for checking verification codes
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOL"

# Reload systemd and enable the service
echo "Enabling and starting the service..."
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot.service
sudo systemctl start telegram-bot.service

# Set up log rotation for the bot
sudo bash -c 'cat > /etc/logrotate.d/telegram-bot << EOL
/var/log/syslog {
    rotate 7
    daily
    missingok
    notifempty
    delaycompress
    compress
    postrotate
        invoke-rc.d rsyslog rotate >/dev/null 2>&1 || true
    endscript
}
EOL'

echo "=== Setup completed! ==="
echo "To check the bot's status, run: sudo systemctl status telegram-bot.service"
echo "To view the bot logs, run: sudo journalctl -u telegram-bot.service -f"