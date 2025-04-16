# TG-Bot

## What is this?
This is a Telegram bot that uses LLM (Large Language Models) like DeepSeek, Grok and ChatGPT. It can answer questions and fetch news from Unwire.hk.

## Requirements
- Python 3.8 or newer
- A Telegram account
- API keys for the LLMs you want to use

## Setup

### Local Setup
1. Clone this repository
2. Create a `.env` file in the `config` folder with your API keys
```
API_ID=your_telegram_api_id
API_HASH=your_telegram_api_hash
PHONE_NUMBER=your_phone_number
ENVIRONMENT=prod
DEEPSEEK_API_KEY=your_deepseek_key
GITHUB_API_KEY=your_github_key
GROK_API_KEY=your_grok_key
```
3. Install the requirements: `pip install -r requirements.txt`

### Azure VM Setup
1. Make sure you have Terraform and Azure CLI installed
2. Run these commands:
```
terraform init
terraform apply
```
4. The VM's IP address will be shown when done

## Demo
Feel free to call me with the command for testing:
https://t.me/SecondarySchoolDog

## Commands
- `/deepseek [question]` - Ask DeepSeek AI a question
- `/r1 [question]` - Use DeepSeek R1 to think step by step
- `/gpt [question]` - Ask ChatGPT a question
- `/grok [question]` - Ask Grok AI a question
- `/grok_think [question]` - Use Grok to think step by step
- `/unwire` - Get Today news from Unwire.hk
- `/unwire 2025-04-15` - Get news from a specific date

## Project Structure
```
TG-bot/
├── config/            # Configuration files
├── scripts/           # Shell scripts
├── src/               # Source code
│   ├── api/           # API integrations
│   ├── services/      # Service modules
│   ├── userbot/       # Telegram bot code
│   └── utils/         # Helper functions
├── main.tf            # Terraform config
└── variables.tf       # Terraform variables
```
