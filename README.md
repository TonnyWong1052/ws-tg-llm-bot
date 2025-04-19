# Multi-Platform LLM Chat Bot

A multi-platform LLM chat bot framework that currently supports Telegram, with plans to support WhatsApp and other platforms in the future.

## Known issue
1. Logging Save Problem

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
│       ├── openai.py
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
│   │   └── commands/       # Command handlers (to be implemented)
│   └── whatsapp/           # WhatsApp platform (future)
│       └── __init__.py
└── main.py                 # Application entry point
```


## Project LLM interface
1. DeepSeek API : https://platform.deepseek.com/usage
2. GitHub API : https://github.com/settings/personal-access-tokens
3. Grok API : Not avabiliable (Custom by myself)

## Installation

1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set up environment variables or create a `config/.env` file:

```
API_ID=your_telegram_api_id
API_HASH=your_telegram_api_hash
PHONE_NUMBER=your_phone_number
OPENAI_API_KEY=your_openai_key
DEEPSEEK_API_KEY=your_deepseek_key
GITHUB_API_KEY=your_github_key
GROK_API_KEY=your_grok_key
ENVIRONMENT=prod  # or 'test' for testing
```

## Running

Start the Telegram bot (default):

```bash
python src/main.py
```

Or specify platforms:

```bash
python src/main.py --platforms telegram
```

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
