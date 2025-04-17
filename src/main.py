import asyncio
import os
import logging
import argparse
import sys

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("main")

# If running as main program, import modules
if __name__ == "__main__":
    from core.config import config
    from api.llm_client import LLMClient
    from api.llm_providers import (
        OpenAIProvider, DeepseekProvider,
        GitHubProvider, GrokProvider
    )
    from platforms.telegram import TelegramBot
    from platforms.telegram.handlers import TelegramMessageHandler
    from userbot.start_userbot import start_userbot  
    
    # Define available platforms
    PLATFORMS = {
        "telegram": TelegramBot,
        "userbot": "UserBot", 
        # "whatsapp": WhatsAppBot  # WhatsApp platform to be added in the future
    }
    
    async def setup_llm_client():
        """
        Set up LLM client and its providers
        """
        llm_client = LLMClient()
        
        # Register LLM providers
        if config.openai_api_key:
            llm_client.register_provider('openai', OpenAIProvider(config.openai_api_key))
        
        if config.deepseek_api_key:
            llm_client.register_provider('deepseek', DeepseekProvider(config.deepseek_api_key))
        
        if config.github_api_key:
            llm_client.register_provider('github', GitHubProvider(config.github_api_key))
        
        if config.grok_api_key:
            llm_client.register_provider('grok', GrokProvider(config.grok_api_key))
        
        return llm_client
    
    async def main():
        """
        Application main entry point
        """
        # Parse command line arguments
        parser = argparse.ArgumentParser(description="Run the bot on specified platforms")
        parser.add_argument(
            '--platforms', '-p',
            type=str,
            default='telegram',
            help=f"Comma-separated list of platforms to run. Available: {', '.join(PLATFORMS.keys())}"
        )
        args = parser.parse_args()
        
        # Initialize LLM client
        llm_client = await setup_llm_client()
        
        # Get platforms to run
        selected_platforms = [p.strip() for p in args.platforms.split(',') if p.strip()]
        
        # Ensure at least one platform is selected
        if not selected_platforms:
            logger.error("No platforms selected. Please specify at least one platform.")
            return 1
        
        # Check if all selected platforms are valid
        invalid_platforms = [p for p in selected_platforms if p not in PLATFORMS]
        if invalid_platforms:
            logger.error(f"Invalid platforms: {', '.join(invalid_platforms)}. "
                        f"Available platforms: {', '.join(PLATFORMS.keys())}")
            return 1
        
        # Handle userbot special case
        if 'userbot' in selected_platforms:
            logger.info("Starting Telegram UserBot...")
            try:
                # Ensure global variables in userbot_tg.py are correctly initialized
                # First import userbot_tg to initialize its global variables
                import userbot.userbot_tg
                # Then check if required variables exist and are correct
                from userbot.userbot_tg import API_ID, API_HASH, PHONE_NUMBER
                from userbot.userbot_tg import ensure_llm_client_initialized
                
                # Check necessary API keys
                if not API_ID or not API_HASH or not PHONE_NUMBER:
                    logger.error("Userbot requires API_ID, API_HASH, and PHONE_NUMBER environment variables. Please check config/.env file.")
                    return 1
                
                # Ensure LLM client is initialized
                ensure_llm_client_initialized()
                
                # Print startup information
                logger.info(f"UserBot environment setup - API_ID: {API_ID}, PHONE: {PHONE_NUMBER[:4]}***")
                
                # Directly run the main function from userbot_tg.py
                from userbot.userbot_tg import main as userbot_main
                await userbot_main()
                return 0  # Exit after userbot finishes running
            except Exception as e:
                logger.error(f"Failed to start UserBot: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return 1
        
        # Initialize bots for selected platforms
        bots = {}
        for platform_name in selected_platforms:
            try:
                bot_class = PLATFORMS[platform_name]
                bot = bot_class()
                await bot.initialize()
                bots[platform_name] = bot
                logger.info(f"Initialized {platform_name} bot")
            except Exception as e:
                logger.error(f"Failed to initialize {platform_name} bot: {e}")
                continue
        
        # Exit if no bots could be initialized
        if not bots:
            logger.error("No bots could be initialized. Exiting.")
            return 1
        
        # Start all bots
        tasks = []
        for platform_name, bot in bots.items():
            try:
                success = await bot.start()
                if success:
                    if platform_name == 'telegram':
                        # Set up message handler for Telegram bot
                        handler = TelegramMessageHandler(bot)
                        # Add run task
                        tasks.append(bot.run())
                    # Other platforms can be added here...
                    logger.info(f"Started {platform_name} bot")
                else:
                    logger.error(f"Failed to start {platform_name} bot")
            except Exception as e:
                logger.error(f"Error starting {platform_name} bot: {e}")
        
        # Wait for all tasks to complete (usually never happens unless bots are terminated)
        if tasks:
            logger.info(f"Running {len(tasks)} bot(s). Press Ctrl+C to stop.")
            await asyncio.gather(*tasks)
        else:
            logger.error("No bots could be started. Exiting.")
            return 1
        
        return 0
    
    # Run the application
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}")
        sys.exit(1) 