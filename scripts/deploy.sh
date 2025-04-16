#!/bin/bash

# Deploy Telegram Bot to Azure using Terraform
# This script automates the deployment process

set -e  # Exit on any error

echo "=== Starting Telegram Bot deployment to Azure ==="

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo "Azure CLI not found. Please install it first."
    echo "Visit: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

# Check if Terraform is installed
if ! command -v terraform &> /dev/null; then
    echo "Terraform not found. Please install it first."
    echo "Visit: https://learn.hashicorp.com/tutorials/terraform/install-cli"
    exit 1
fi

# Navigate to the project root directory
cd "$(dirname "$0")/.." || exit
PROJECT_ROOT=$(pwd)

# Check if .env file exists in root directory
if [ -f ".env" ]; then
    echo "Found .env file in root directory"
    # Check if config directory exists
    if [ ! -d "config" ]; then
        echo "Creating config directory..."
        mkdir -p config
    fi
    # Copy .env to config directory if not already there
    if [ ! -f "config/.env" ]; then
        echo "Copying .env to config directory..."
        cp .env config/.env
    fi
fi

# Log in to Azure if not already logged in
az account show &> /dev/null || az login

# Initialize Terraform
echo "=== Initializing Terraform ==="
terraform init

# Create a Terraform plan
echo "=== Creating Terraform plan ==="
terraform plan -out=tfplan

# Apply the Terraform plan
echo "=== Applying Terraform plan ==="
terraform apply "tfplan"

# Get the VM's IP address
VM_IP=$(terraform output -raw vm_public_ip)
echo "=== Deployment completed successfully! ==="
echo "Your Telegram bot is now running on VM with IP: $VM_IP"
echo "To check the bot's status, SSH into the VM and run:"
echo "  sudo systemctl status telegram-bot.service"
echo "To view the bot's logs, run:"
echo "  sudo journalctl -u telegram-bot.service"
echo ""
echo "Note: The first time you connect, you may need to enter the Telegram verification code."
echo "To do this, SSH into the VM and check the service logs."