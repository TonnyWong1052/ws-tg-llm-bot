"""
Module for starting the Telegram UserBot

This module provides functions to start the Telegram UserBot.
"""

import asyncio
import sys
import os
import logging

logger = logging.getLogger("userbot_starter")

async def start_userbot():
    """
    Start the Telegram UserBot
    
    This function imports the main function from userbot_tg.py and executes it
    """
    try:
        # Use global variables from userbot_tg.py
        import sys
        import os
        from .userbot_tg import main as userbot_main
        from .userbot_tg import API_ID, API_HASH, PHONE_NUMBER, llm_client, client

        # Ensure client and llm_client are properly initialized in userbot_tg.py
        logger.info("Starting Telegram UserBot...")
        
        # Ensure API_ID and API_HASH are set
        if not API_ID or not API_HASH:
            logger.error("API_ID or API_HASH not set. Please ensure environment variables are properly configured.")
            return False
        
        # Ensure phone number is set
        if not PHONE_NUMBER:
            logger.error("PHONE_NUMBER not set. Please ensure environment variables are properly configured.")
            return False

        # Execute the main function of the UserBot
        await userbot_main()
        
        return True
    except Exception as e:
        logger.error(f"Error starting UserBot: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    # If this file is run directly, start the UserBot
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        asyncio.run(start_userbot())
    except KeyboardInterrupt:
        print("\shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}")
        sys.exit(1) 