import asyncio
import logging
from telethon.errors.rpcerrorlist import FloodWaitError
from .utils import MessageHelper, FloodWaitHandler

logger = logging.getLogger("telegram_commands")

class CommandHandler:
    """
    Base class for Telegram command handlers, providing shared functionality and properties
    """
    
    def __init__(self, client, llm_client=None):
        """
        Initialize the command handler
        
        Args:
            client: Telegram client (standard bot or UserBot)
            llm_client: LLM client instance (optional)
        """
        self.client = client
        self.llm_client = llm_client
        self.message_helper = MessageHelper()
        self.flood_handler = FloodWaitHandler()
        
    async def handle_flood_wait_error(self, event, e, message=None):
        """
        Handle FloodWaitError
        
        Args:
            event: Triggering event
            e: FloodWaitError exception
            message: Custom message (optional)
            
        Returns:
            None
        """
        wait_seconds = e.seconds
        logger.warning(f"FloodWaitError: {wait_seconds}s wait required")
        
        # Custom message or default message
        response = message or f"Telegram rate limit triggered, need to wait {wait_seconds} seconds. Please try again later."
        
        try:
            await event.respond(response)
        except Exception as respond_error:
            logger.error(f"Unable to send rate limit notification: {respond_error}")
            
    async def handle_error(self, event, error, message=None):
        """
        Handle general errors
        
        Args:
            event: Triggering event
            error: Exception object
            message: Custom message (optional)
            
        Returns:
            None
        """
        error_str = str(error)
        logger.error(f"Error in command handler: {error_str}")
        
        # Custom message or default message
        response = message or f"Error occurred: {error_str}"
        
        try:
            await event.reply(response)
        except Exception as reply_error:
            logger.error(f"Unable to send error message: {reply_error}")
            
    async def register_handlers(self):
        """
        Register command handlers, should be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement register_handlers method")
    
    @staticmethod
    async def create_llm_task(llm_client, provider, prompt, **kwargs):
        """
        Create non-blocking LLM task
        
        Args:
            llm_client: LLM client
            provider: Provider name
            prompt: Prompt
            **kwargs: Additional parameters
            
        Returns:
            Task: Async task
        """
        return asyncio.create_task(
            asyncio.to_thread(llm_client.call_llm, provider, prompt, **kwargs)
        ) 