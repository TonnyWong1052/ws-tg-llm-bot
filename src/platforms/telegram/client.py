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
        self.handlers = {}  # Dictionary to store command tasks
        self.active_tasks = set()  # Set to track active tasks
        self.task_messages = {}  # Dictionary to store task messages
        self.task_start_times = {}  # Dictionary to store task start times
        self.logger = logger
        self.llm_client = None
    
    async def initialize(self):
        """
        Initialize Telegram client
        """
        self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
        
        # Initialize LLM client
        await self._initialize_llm_client()
        
        # Register command handlers
        await self._register_handlers()
        
        self.logger.info("Telegram bot initialized")
    
    async def _initialize_llm_client(self):
        """
        Initialize LLM client
        """
        try:
            from api.llm_client import LLMClient
            self.llm_client = LLMClient()
            self.logger.info("LLM client initialized successfully")
            
            # Check registered providers
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
        Register all command handlers
        """
        # Register basic command handlers
        basic_handler = BasicCommandHandler(self, self.llm_client)
        await basic_handler.register_handlers()
        self.logger.info("Basic command handlers registered")
        
        # Register LLM command handlers
        if self.llm_client:
            self.logger.info("Initializing LLM command handlers")
            llm_handler = LLMCommandHandler(self, self.llm_client)
            await llm_handler.register_handlers()
            self.logger.info("LLM command handlers registered")
        else:
            self.logger.warning("LLM client not initialized, LLM commands will not be available")
    
    async def _monitor_tasks(self):
        """
        Monitor active tasks and clean up completed or failed tasks
        """
        while True:
            try:
                # Check all active tasks
                for task in list(self.active_tasks):
                    if task.done():
                        # Remove from active tasks
                        self.active_tasks.discard(task)
                        
                        # Get task ID and clean up
                        for task_id, t in list(self.handlers.items()):
                            if t == task:
                                self.handlers.pop(task_id, None)
                                message = self.task_messages.pop(task_id, None)
                                start_time = self.task_start_times.pop(task_id, None)
                                
                                # Log completion time if we have start time
                                if start_time:
                                    duration = time.time() - start_time
                                    self.logger.info(f"Task {task_id} completed in {duration:.2f} seconds")
                                
                                # Handle any exceptions
                                if task.exception():
                                    self.logger.error(f"Task {task_id} failed: {task.exception()}")
                                    if message:
                                        try:
                                            await message.edit(f"Error: {str(task.exception())}")
                                        except:
                                            pass
                                break
                
                await asyncio.sleep(1)  # Check every second
            except Exception as e:
                self.logger.error(f"Error in task monitor: {e}")
                await asyncio.sleep(5)  # Wait longer on error
    
    async def start(self):
        """
        Start the Telegram bot
        """
        await super().start()
        
        # Start task monitor
        self.monitor_task = asyncio.create_task(self._monitor_tasks())
        
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
        # Cancel monitor task
        if hasattr(self, 'monitor_task'):
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        # Cancel all active tasks
        for task in self.active_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
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
    
    def add_event_handler(self, callback, event_type):
        """
        Add an event handler to the Telegram client
        
        Args:
            callback: The callback function to handle the event
            event_type: The event type to handle
        """
        self.client.add_event_handler(callback, event_type)
    
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