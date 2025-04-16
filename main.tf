# Configure the Azure provider
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
  required_version = ">= 1.1.0"
}

provider "azurerm" {
  features {}
}

# Create a resource group
resource "azurerm_resource_group" "tg_bot_rg" {
  name     = var.resource_group_name
  location = var.location
  tags = {
    Environment = var.environment
    Project     = "TelegramBot"
  }
}

# Create a virtual network
resource "azurerm_virtual_network" "tg_bot_vnet" {
  name                = "telegram-bot-network"
  address_space       = ["10.0.0.0/16"]
  location            = azurerm_resource_group.tg_bot_rg.location
  resource_group_name = azurerm_resource_group.tg_bot_rg.name
}

# Create subnet
resource "azurerm_subnet" "tg_bot_subnet" {
  name                 = "internal"
  resource_group_name  = azurerm_resource_group.tg_bot_rg.name
  virtual_network_name = azurerm_virtual_network.tg_bot_vnet.name
  address_prefixes     = ["10.0.2.0/24"]
}

# Create public IP
resource "azurerm_public_ip" "tg_bot_pip" {
  name                = "telegram-bot-public-ip"
  location            = azurerm_resource_group.tg_bot_rg.location
  resource_group_name = azurerm_resource_group.tg_bot_rg.name
  allocation_method   = "Dynamic"
}

# Create Network Security Group and rules
resource "azurerm_network_security_group" "tg_bot_nsg" {
  name                = "telegram-bot-nsg"
  location            = azurerm_resource_group.tg_bot_rg.location
  resource_group_name = azurerm_resource_group.tg_bot_rg.name

  security_rule {
    name                       = "SSH"
    priority                   = 1001
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "HTTPS"
    priority                   = 1002
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

# Create network interface
resource "azurerm_network_interface" "tg_bot_nic" {
  name                = "telegram-bot-nic"
  location            = azurerm_resource_group.tg_bot_rg.location
  resource_group_name = azurerm_resource_group.tg_bot_rg.name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.tg_bot_subnet.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.tg_bot_pip.id
  }
}

# Connect the security group to the network interface
resource "azurerm_network_interface_security_group_association" "tg_bot_assoc" {
  network_interface_id      = azurerm_network_interface.tg_bot_nic.id
  network_security_group_id = azurerm_network_security_group.tg_bot_nsg.id
}

# Create virtual machine
resource "azurerm_linux_virtual_machine" "tg_bot_vm" {
  name                  = "telegram-bot-vm"
  location              = azurerm_resource_group.tg_bot_rg.location
  resource_group_name   = azurerm_resource_group.tg_bot_rg.name
  network_interface_ids = [azurerm_network_interface.tg_bot_nic.id]
  size                  = var.vm_size

  os_disk {
    name                 = "telegram-bot-osdisk"
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }

  computer_name  = "botvm"
  admin_username = var.admin_username

  admin_ssh_key {
    username   = var.admin_username
    public_key = file(var.ssh_public_key_path)
  }

  # Initialize connection details for all provisioners
  connection {
    type        = "ssh"
    user        = var.admin_username
    private_key = file(replace(var.ssh_public_key_path, ".pub", ""))
    host        = azurerm_public_ip.tg_bot_pip.ip_address
  }

  # Create directory structure
  provisioner "remote-exec" {
    inline = [
      "mkdir -p ~/TG-bot/src/userbot",
      "mkdir -p ~/TG-bot/src/api",
      "mkdir -p ~/TG-bot/src/utils",
      "mkdir -p ~/TG-bot/src/services",
      "mkdir -p ~/TG-bot/config",
      "mkdir -p ~/TG-bot/scripts",
      "mkdir -p ~/TG-bot/logs"
    ]
  }

  # Copy project files to VM
  provisioner "file" {
    source      = "./src/userbot/userbot_tg.py"
    destination = "~/TG-bot/src/userbot/userbot_tg.py"
  }

  provisioner "file" {
    source      = "./src/api/llm_api.py"
    destination = "~/TG-bot/src/api/llm_api.py"
  }

  provisioner "file" {
    source      = "./src/utils/animations.py"
    destination = "~/TG-bot/src/utils/animations.py"
  }

  provisioner "file" {
    source      = "./src/services/unwire_fetch.py"
    destination = "~/TG-bot/src/services/unwire_fetch.py"
  }

  provisioner "file" {
    source      = "./config/.env"
    destination = "~/TG-bot/config/.env"
  }

  provisioner "file" {
    source      = "./scripts/setup.sh"
    destination = "~/TG-bot/scripts/setup.sh"
  }

  provisioner "file" {
    source      = "./scripts/run_tg_bot.sh"
    destination = "~/TG-bot/scripts/run_tg_bot.sh"
  }

  provisioner "file" {
    source      = "./requirements.txt"
    destination = "~/TG-bot/requirements.txt"
  }

  provisioner "file" {
    source      = "./session_name.session"
    destination = "~/TG-bot/session_name.session"
  }

  # Create a startup script that will run the bot in the background
  provisioner "file" {
    content     = <<-EOT
#!/bin/bash
# This script starts the Telegram bot in the background
cd ~/TG-bot
# Create virtual environment if not exists
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Check if bot is already running
if pgrep -f "python.*userbot_tg.py" > /dev/null; then
    echo "Bot is already running. Restarting..."
    pkill -f "python.*userbot_tg.py"
    sleep 2
fi

# Start bot in the background
echo "Starting Telegram bot in the background ($(date))" >> ~/TG-bot/logs/startup.log
cd ~/TG-bot && nohup python3 src/userbot/userbot_tg.py > ~/TG-bot/logs/output.log 2>&1 &

# Log the process ID
echo "Bot started with PID $! ($(date))" >> ~/TG-bot/logs/startup.log
echo $! > ~/TG-bot/bot.pid
EOT
    destination = "~/TG-bot/scripts/start_bot.sh"
  }

  # Make scripts executable
  provisioner "remote-exec" {
    inline = [
      "chmod +x ~/TG-bot/scripts/*.sh",
    ]
  }

  # Set up the bot to start automatically when the VM boots
  provisioner "file" {
    content     = <<-EOT
[Unit]
Description=Telegram Bot Service
After=network.target

[Service]
ExecStart=/bin/bash /home/${var.admin_username}/TG-bot/scripts/start_bot.sh
WorkingDirectory=/home/${var.admin_username}/TG-bot
User=${var.admin_username}
StandardOutput=append:/home/${var.admin_username}/TG-bot/logs/service.log
StandardError=append:/home/${var.admin_username}/TG-bot/logs/service.log

[Install]
WantedBy=multi-user.target
EOT
    destination = "/tmp/telegram-bot.service"
  }

  # Configure systemd service and install dependencies
  provisioner "remote-exec" {
    inline = [
      "sudo apt-get update",
      "sudo apt-get install -y python3-pip python3-venv tmux screen",
      "sudo mv /tmp/telegram-bot.service /etc/systemd/system/",
      "sudo systemctl daemon-reload",
      "sudo systemctl enable telegram-bot.service",
      "sudo systemctl start telegram-bot.service",
      "echo 'Bot service has been started and enabled to run at boot time.'"
    ]
  }
}

# Output the public IP of the VM
output "vm_public_ip" {
  value       = azurerm_public_ip.tg_bot_pip.ip_address
  description = "The public IP address of the Telegram bot VM"
}