variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
  default     = "telegram-bot-resources"
}

variable "location" {
  description = "Azure region to deploy resources"
  type        = string
  default     = "eastus"
}

variable "environment" {
  description = "Environment name (prod or test)"
  type        = string
  default     = "prod"
}

variable "vm_size" {
  description = "Size of the virtual machine"
  type        = string
  default     = "Standard_B1s"  # This is a cost-effective size for a bot
}

variable "admin_username" {
  description = "Username for the VM admin account"
  type        = string
  default     = "azureuser"
}

variable "ssh_public_key_path" {
  description = "Path to the SSH public key file"
  type        = string
  default     = "~/.ssh/id_rsa.pub"
}