import asyncio
import logging
import os
import re
import sys
import time
import io
from telethon import TelegramClient, events
from telethon.errors.rpcerrorlist import FloodWaitError

from core.bot_base import BotBase
from core.config import config
from core.message_handler import StreamHandler
from utils.animations import animated_thinking, INITIAL_MESSAGE_ART, SIMPLE_INITIAL_MESSAGE
from .commands import (
    BasicCommandHandler,
    LLMCommandHandler,
    MessageHelper,
    FloodWaitHandler
)

logger = logging.getLogger("telegram_bot")

class TelegramBot(BotBase):
    """
    Telegram platform bot implementation
    """
    def __init__(self):
        """
        Initialize Telegram bot
        """
        super().__init__("telegram")
        self.api_id = config.api_id
        self.api_hash = config.api_hash
        self.phone_number = config.phone_number
        self.session_name = 'session_name'
        self.client = None
        self.flood_handler = FloodWaitHandler()
        self.stream_handler = StreamHandler(config.telegram_max_length)
        self.message_helper = MessageHelper()
        self.handlers = {}
        self.logger = logger
        self.llm_client = None
    
    async def initialize(self):
        """
        Initialize Telegram client
        """
        self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
        
        # 初始化 LLM 客戶端
        await self._initialize_llm_client()
        
        # 註冊命令處理程序
        await self._register_handlers()
        
        self.logger.info("Telegram bot initialized")
    
    async def _initialize_llm_client(self):
        """
        初始化 LLM 客戶端
        """
        try:
            from api.llm_client import LLMClient
            self.llm_client = LLMClient()
            self.logger.info("LLM client initialized successfully")
            
            # 檢查已註冊的提供者
            if hasattr(self.llm_client, 'providers'):
                self.logger.info(f"Registered providers: {list(self.llm_client.providers.keys())}")
            else:
                self.logger.warning("LLM client has no providers attribute")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize LLM client: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
    
    async def _register_handlers(self):
        """
        註冊所有命令處理程序
        """
        # 註冊基本命令處理程序
        basic_handler = BasicCommandHandler(self.client, self.llm_client)
        await basic_handler.register_handlers()
        self.logger.info("Basic command handlers registered")
        
        # 註冊 LLM 命令處理程序
        if self.llm_client:
            self.logger.info("Initializing LLM command handlers")
            llm_handler = LLMCommandHandler(self.client, self.llm_client)
            await llm_handler.register_handlers()
            self.logger.info("LLM command handlers registered")
        else:
            self.logger.warning("LLM client not initialized, LLM commands will not be available")
    
    async def start(self):
        """
        Start the Telegram bot
        """
        await super().start()
        
        # Check if we're running in a non-interactive environment (e.g., server)
        is_interactive = os.isatty(sys.stdin.fileno()) if hasattr(sys, 'stdin') and hasattr(sys.stdin, 'fileno') else False
        
        if not is_interactive:
            self.logger.info("Running in non-interactive mode, using session-only authentication")
            # In non-interactive mode, use existing session only
            try:
                # Start without phone number to avoid code prompt
                await self.client.start()
                if not await self.client.is_user_authorized():
                    self.logger.error("Not authorized and cannot request code in non-interactive mode")
                    self.logger.error("Please run scripts/setup_session.py on a machine with an interactive terminal first")
                    return False
            except Exception as e:
                self.logger.error(f"Failed to start client in non-interactive mode: {str(e)}")
                return False
        else:
            # Interactive mode - normal flow with phone parameter
            try:
                await self.client.start(phone=self.phone_number)
            except Exception as e:
                self.logger.error(f"Error starting client: {str(e)}")
                return False
        
        self.logger.info("Telegram bot is running...")
        return True
    
    async def stop(self):
        """
        Stop the Telegram bot
        """
        await super().stop()
        if self.client:
            await self.client.disconnect()
        self.logger.info("Telegram bot stopped")
    
    async def safe_send_message(self, message_obj, text, event=None, parse_mode=None):
        """
        Safely send a message, handling long messages and errors
        
        Args:
            message_obj: The message object to edit
            text (str): The text to send
            event: Original event object (for fallback)
            parse_mode: Text parsing mode
            
        Returns:
            bool: True if successfully sent
        """
        return await self.message_helper.safe_send_message(message_obj, text, event=event, parse_mode=parse_mode)
    
    async def send_message(self, chat_id, text, **kwargs):
        """
        Send a new message
        
        Args:
            chat_id: Chat ID
            text: Message text
            **kwargs: Additional parameters
            
        Returns:
            Message: The sent message object
        """
        return await self.client.send_message(chat_id, text, **kwargs)
    
    async def edit_message(self, message, text, **kwargs):
        """
        Edit a message
        
        Args:
            message: Message object
            text: New message text
            **kwargs: Additional parameters
            
        Returns:
            Message: The edited message object
        """
        return await message.edit(text, **kwargs)
    
    async def send_file(self, chat_id, file, **kwargs):
        """
        Send a file
        
        Args:
            chat_id: Chat ID
            file: File object or path
            **kwargs: Additional parameters
            
        Returns:
            Message: The sent message object
        """
        return await self.client.send_file(chat_id, file, **kwargs)
    
    async def run(self):
        """
        Run the bot until disconnected
        """
        await self.client.run_until_disconnected()
    
    async def create_llm_task(self, provider, prompt, **kwargs):
        """
        Create an async task for communicating with LLM
        
        Args:
            provider: LLM provider
            prompt: Prompt
            **kwargs: Additional parameters
            
        Returns:
            Task: Async task
        """
        if not self.llm_client:
            self.logger.error("LLM client not initialized")
            raise ValueError("LLM client not initialized")
        
        return asyncio.create_task(
            asyncio.to_thread(self.llm_client.call_llm, provider, prompt, **kwargs)
        )
    
    async def handle_llm_request(self, event, provider, prompt, model_name=None, system_prompt=None, display_name=None):
        """
        Handle LLM request
        
        Args:
            event: Telegram event object
            provider: LLM provider
            prompt: Prompt
            model_name: Model name
            system_prompt: System prompt
            display_name: Display name
            
        Returns:
            None
        """
        response_message = None
        
        try:
            # Send initial response message
            response_message = await event.respond("Processing, please wait...")
            
            # Ensure LLM client is initialized
            if not self.llm_client:
                await response_message.edit("LLM client not initialized, cannot process request.")
                return
            
            model = model_name if model_name else provider
            
            # Get appropriate stream generator based on provider
            stream_generator = self.llm_client.call_llm_stream(provider, prompt, model=model)
            
            # Process stream and update message - increased update interval to 3.0 seconds to avoid repetition issues
            await MessageHelper.process_stream_with_updates(
                message_obj=response_message, 
                stream_generator=stream_generator,
                min_update_interval=3.0  # Increased from default 1.5 seconds
            )
            
        except FloodWaitError as e:
            await self.handle_flood_wait_error(event, e, response_message)
            
        except Exception as e:
            self.logger.error(f"Error in handle_llm_request: {e}")
            import traceback
            traceback.print_exc()
            
            # Try to send error message
            await self.handle_error(event, e, response_message)
    
    async def handle_flood_wait_error(self, event, e, response_message=None):
        """
        Handle FloodWaitError error
        
        Args:
            event: Triggering event
            e: FloodWaitError exception
            response_message: Response message object (optional)
        """
        wait_seconds = e.seconds
        self.logger.warning(f"FloodWaitError in handle_llm_request: {wait_seconds}s wait required")
        
        try:
            if response_message:
                await response_message.edit(f"Telegram rate limit triggered, need to wait {wait_seconds} seconds. Please try again later.")
            else:
                await event.respond(f"Telegram rate limit triggered, need to wait {wait_seconds} seconds. Please try again later.")
        except Exception as edit_error:
            self.logger.error(f"Unable to edit/send rate limit message: {edit_error}")
            
    async def handle_error(self, event, e, response_message=None):
        """
        Handle general errors
        
        Args:
            event: Triggering event
            e: Exception object
            response_message: Response message object (optional)
        """
        try:
            if response_message:
                await response_message.edit(f"Error occurred: {str(e)}")
            else:
                await event.reply(f"Error occurred: {str(e)}")
        except Exception as reply_error:
            self.logger.error(f"Unable to send error message: {reply_error}")