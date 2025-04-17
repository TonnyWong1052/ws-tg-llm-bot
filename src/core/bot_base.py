from abc import ABC, abstractmethod
import asyncio
import os
import time
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class BotBase(ABC):
    """
    Base abstract class for chat bots, all platform-specific bot implementations should inherit from this
    """
    def __init__(self, platform_name):
        """
        Initialize the base bot
        
        Args:
            platform_name (str): Platform name (e.g., 'telegram', 'whatsapp')
        """
        self.platform = platform_name
        self.logger = logging.getLogger(f"{platform_name}_bot")
        self.commands = {}
        self.client = None
        self.is_running = False
        self.start_time = None
    
    @abstractmethod
    async def initialize(self):
        """
        Initialize platform-specific client for the bot
        """
        pass
    
    @abstractmethod
    async def start(self):
        """
        Start the bot service
        """
        self.start_time = time.time()
        self.is_running = True
        self.logger.info(f"{self.platform.capitalize()} bot is starting")
    
    @abstractmethod
    async def stop(self):
        """
        Stop the bot service
        """
        self.is_running = False
        uptime = time.time() - self.start_time if self.start_time else 0
        self.logger.info(f"{self.platform.capitalize()} bot is stopping. Uptime: {uptime:.2f} seconds")
    
    def register_command(self, command_name, handler_func):
        """
        Register a command handler
        
        Args:
            command_name (str): Command name (without the '/' prefix)
            handler_func (callable): Function to handle the command
        """
        self.commands[command_name] = handler_func
        self.logger.info(f"Registered command: {command_name}")
    
    def get_uptime(self):
        """
        Get the uptime of the bot
        
        Returns:
            float: Uptime in seconds
        """
        if not self.start_time:
            return 0
        return time.time() - self.start_time
    
    @abstractmethod
    async def send_message(self, chat_id, text, **kwargs):
        """
        Send a message to a specific chat
        
        Args:
            chat_id: Chat identifier
            text (str): Message text
            **kwargs: Additional platform-specific parameters
        """
        pass
    
    @abstractmethod
    async def edit_message(self, message, text, **kwargs):
        """
        Edit an existing message
        
        Args:
            message: Message object or identifier
            text (str): New message text
            **kwargs: Additional platform-specific parameters
        """
        pass
    
    @abstractmethod
    async def send_file(self, chat_id, file, **kwargs):
        """
        Send a file to a specific chat
        
        Args:
            chat_id: Chat identifier
            file: File object or path
            **kwargs: Additional platform-specific parameters
        """
        pass 