#!/bin/bash
# Activate conda base environment
echo "Activating conda base environment..."
source ~/miniconda3/bin/activate base || source ~/anaconda3/bin/activate base || conda activate base

# Navigate to the project root directory
cd "$(dirname "$0")/.." || exit
PROJECT_ROOT=$(pwd)

# Install required packages
echo "Installing required packages..."
sudo pip install -r requirements.txt

# Make sure the config directory exists
mkdir -p config

# If .env file exists in root, move it to config directory
if [ -f ".env" ]; then
    echo "Moving .env file to config directory..."
    mv .env config/.env
fi

# Run the Telegram bot
echo "Starting the Telegram bot..."
python src/userbot/userbot_tg.py
