# Multi-Platform LLM Chat Bot

A multi-platform LLM chat bot framework that currently supports Telegram, with plans to support WhatsApp and other platforms in the future.

## Features

- Multi-platform support (currently Telegram)
- Multiple LLM provider integrations (DeepSeek, GitHub, Grok)
- Automatic restart and monitoring
- Comprehensive logging system
- Modular command system
- Extensible platform architecture

## Azure Easy Deployment 
1. config `config/.env` file
2. Deploy the project in Azure server (SCP)
```bash
scripts/az_deploy.sh
```


## Directory Structure

```
src/
├── core/                   # Core framework components
│   ├── __init__.py
│   ├── config.py           # Configuration loading and management
│   ├── bot_base.py         # Base bot class
│   ├── message_handler.py  # Basic message handling logic
│   └── command_registry.py # Command registration system
├── api/                    # API clients and providers
│   ├── __init__.py
│   ├── llm_client.py       # Unified LLM client
│   └── llm_providers/      # Specific implementations for LLM providers
│       ├── __init__.py
│       ├── deepseek.py
│       ├── github.py
│       └── grok.py
├── utils/                  # Utility functions
│   ├── __init__.py
│   └── animations.py       # Animation and UI-related features
├── services/               # External service integrations
│   ├── __init__.py
│   └── unwire_fetch.py     # Unwire news service
├── platforms/              # Platform-specific implementations
│   ├── __init__.py
│   ├── telegram/           # Telegram platform
│   │   ├── __init__.py
│   │   ├── client.py       # Telegram client
│   │   ├── handlers.py     # Message handlers
│   │   └── commands/       # Command handlers
│   └── whatsapp/           # WhatsApp platform (future)
│       └── __init__.py
└── main.py                 # Application entry point
```

## LLM Provider Interfaces

1. DeepSeek API
   - Documentation: https://platform.deepseek.com/usage
   - Features: High performance, stable and reliable
   - Limitations: Requires API key

2. GitHub API
   - Setup: https://github.com/settings/personal-access-tokens
   - Features: Integration with GitHub ecosystem
   - Limitations: Requires personal access token

3. Grok API
   - Status: Not available (Custom implementation)
   - Features: Custom functionality
   - Limitations: Internal use only

## Installation Guide

### Prerequisites
- Python 3.8 or higher
- pip package manager
- Git

### Installation Steps

1. Clone the repository:
```bash
git clone https://github.com/yourusername/ws-tg-llm-bot.git
cd ws-tg-llm-bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
Create a `config/.env` file with the following content:
```env
# Telegram Configuration
API_ID=your_telegram_api_id
API_HASH=your_telegram_api_hash
PHONE_NUMBER=your_phone_number

# LLM API Keys
OPENAI_API_KEY=your_openai_key
DEEPSEEK_API_KEY=your_deepseek_key
GITHUB_API_KEY=your_github_key
GROK_API_KEY=your_grok_key

# Environment Settings
ENVIRONMENT=prod  # or 'test' for testing

# Azure Deployment Variables
AZURE_RESOURCE_GROUP="YOUR_AZURE_RESOURCE_GROUP"
AZURE_VM_NAME="YOUR_Azure_VM_NAME"
AZURE_SUBSCRIPTION_ID="Az_Subscription_ID"
AZURE_VM_IP="YOUR_AZURE_VM_IP"
AZURE_VM_USER="YOUR_AZURE_VM_USER"
SSH_KEY_PATH="You_Pem_File_Here"
```

## Running Guide

### Basic Run
Start the Telegram bot (default):
```bash
python src/main.py
```

### Platform-Specific Run
```bash
python src/main.py --platforms telegram
```

### Using Deployment Scripts
1. Deploy to Azure:
```bash
bash scripts/az_deploy.sh
```

2. Run the bot:
```bash
bash scripts/run_bot.sh
```

3. Stop the bot:
```bash
bash scripts/stop_bot.sh
```

4. Check status:
```bash
bash scripts/check_status.sh
```

## Known Issues
1. Logging Save Problem: In some cases, log files may not be saved correctly
2. Session file validation needs periodic checking


## Adding a New Platform

1. Create a new platform directory under `src/platforms/`
2. Implement platform-specific client and handlers
3. Register the new platform in `src/main.py`

## Adding New Commands

Use the command registry decorator:
```python
from core.command_registry import command_registry

@command_registry.register('example', description='Example command')
async def example_handler(event):
    await event.reply('This is an example command!')
```