import asyncio
import logging
import io
import re
from telethon import events
from telethon.errors.rpcerrorlist import FloodWaitError

from core.message_handler import MessageHandler
from core.command_registry import command_registry
from utils.animations import animated_thinking, INITIAL_MESSAGE_ART, SIMPLE_INITIAL_MESSAGE

logger = logging.getLogger("telegram_handlers")

class TelegramMessageHandler(MessageHandler):
    """
    Message handler for the Telegram platform
    """
    def __init__(self, bot):
        """
        Initialize Telegram message handler
        
        Args:
            bot: TelegramBot instance
        """
        super().__init__(bot)
        self._register_command_handlers()
    
    def _register_command_handlers(self):
        """
        Register command handlers to the Telegram client
        """
        # Register command handlers
        for cmd_name, cmd_info in command_registry.commands.items():
            if not cmd_info.get('platform') or cmd_info.get('platform') == 'telegram':
                self._register_command(cmd_name, cmd_info)
        
        # Register Telegram-specific commands
        for cmd_name, cmd_info in command_registry.platform_handlers.get('telegram', {}).items():
            self._register_command(cmd_name, cmd_info)
        
        # Register help command
        @self.bot.client.on(events.NewMessage(pattern=r'^/help(?:\s+(.+))?$'))
        async def help_handler(event):
            args = event.pattern_match.group(1)
            if args:
                # Display help for a specific command
                command_name = args.strip()
                help_text = command_registry.get_help_text(command_name, 'telegram')
                await event.reply(help_text)
            else:
                # Display help for all commands
                help_text = command_registry.get_help_text(platform='telegram')
                await event.reply(help_text)
    
    def _register_command(self, cmd_name, cmd_info):
        """
        Register a single command handler
        
        Args:
            cmd_name: Command name
            cmd_info: Command information
        """
        pattern = cmd_info['pattern']
        
        @self.bot.client.on(events.NewMessage(pattern=pattern))
        async def command_handler(event):
            await self.handle_command(cmd_name, event)
        
        # Store handler reference
        self.bot.handlers[cmd_name] = command_handler
        logger.info(f"Registered handler for command: {cmd_name}")
    
    async def handle_message(self, message, **kwargs):
        """
        Handle received messages
        
        Args:
            message: Telegram message object
            **kwargs: Additional parameters
        """
        # Check if it's a command
        if message.text and message.text.startswith('/'):
            cmd_info, match = command_registry.match_command(message.text, 'telegram')
            if cmd_info:
                await self.handle_command(cmd_info['name'], message, match=match)
                return
            
            # Unknown command
            await message.reply("Unknown command. Type /help to see available commands.")
            return
        
        # Non-command messages - can be implemented as needed
        # await message.reply("I only respond to commands. Type /help to see available commands.")
    
    async def handle_command(self, command, event, **kwargs):
        """
        Handle command messages
        
        Args:
            command: Command name
            event: Telegram event object
            **kwargs: Additional parameters
        """
        match = kwargs.get('match')
        
        cmd_info = command_registry.get_command(command, 'telegram')
        if not cmd_info:
            await event.reply(f"Command /{command} not found or not available for Telegram.")
            return
        
        try:
            # Call the command handler
            if match:
                # If a match object is provided, use it
                await cmd_info['handler'](event, match)
            else:
                # Otherwise call the handler directly
                await cmd_info['handler'](event)
        except Exception as e:
            logger.error(f"Error handling command {command}: {e}")
            await event.reply(f"Error executing command /{command}: {str(e)}")
    
    async def handle_llm_request(self, event, provider, prompt, model_name=None, system_prompt=None, display_name=None):
        """
        Helper method for handling LLM requests
        
        Args:
            event: Telegram event object
            provider: LLM provider
            prompt: Prompt
            model_name: Model name
            system_prompt: System prompt
            display_name: Display name
        """
        # Log the LLM request
        logger.info(f"LLM Request: Provider={provider}, Model={model_name or 'default'}")
        logger.info(f"Prompt: {prompt[:100]}..." if len(prompt) > 100 else f"Prompt: {prompt}")
        if system_prompt:
            logger.info(f"System prompt: {system_prompt[:100]}..." if len(system_prompt) > 100 else f"System prompt: {system_prompt}")
        
        # Pass the request to the bot handler
        response = await self.bot.handle_llm_request(
            event, provider, prompt, model_name, system_prompt, display_name
        )
        
        # Log the response (if available)
        if response:
            logger.info(f"LLM Response received from {provider} ({model_name or 'default'}):")
            logger.info(f"Response: {response[:150]}..." if len(response) > 150 else f"Response: {response}")
        
        return response
    
    async def handle_grok_stream_request(self, event, prompt):
        """
        Handle Grok streaming requests
        
        Args:
            event: Telegram event object
            prompt: Prompt
        """
        from api.llm_client import LLMClient
        llm_client = LLMClient()
        
        try:
            thinking_msg = await event.reply(INITIAL_MESSAGE_ART)
        except FloodWaitError as e:
            logger.warning(f"FloodWaitError with art message: {e.seconds} seconds wait required. Using simple message instead.")
            await asyncio.sleep(2)
            thinking_msg = await event.reply(SIMPLE_INITIAL_MESSAGE)
        except Exception as e:
            logger.error(f"Error sending initial message: {e}. Using simple message instead.")
            thinking_msg = await event.reply(SIMPLE_INITIAL_MESSAGE)
        
        error_occurred = False
        max_retries = 3
        retry_delay = 2
        
        try:
            if llm_client.environment.lower() == 'test':
                test_task = asyncio.create_task(
                    asyncio.to_thread(llm_client._call_test, prompt)
                )
                response = await animated_thinking(thinking_msg, test_task)
                await self.bot.safe_send_message(thinking_msg, response)
                return
                
            # Check if Grok API key is available
            if not llm_client.providers.get('grok') or not llm_client.providers['grok'].api_key:
                error_msg = "Grok API key not found. Please set GROK_API_KEY in your environment variables or credentials file."
                await self.bot.safe_send_message(thinking_msg, error_msg, event=event)
                return
                
            model = "grok-3-reasoner"
            system_prompt = "You are a helpful AI assistant with reasoning capabilities. Think through problems step by step and explore different aspects of the question. Format your response clearly with proper spacing, line breaks, and structure. Use markdown-style formatting like *bold*, _italic_, and `code` for emphasis. Use numbered lists (1., 2., 3.) and bullet points (- or *) for lists. Ensure your response is well-structured and easy to read."
            
            # Start animation
            animation_task = asyncio.create_task(self._show_limited_thinking_animation(thinking_msg))
            
            # Try using Grok API
            grok_success = False
            for attempt in range(max_retries):
                try:
                    # Set timeout for API call
                    stream_generator = llm_client.call_llm_stream('grok', prompt, system_prompt=system_prompt, model_name=model)
                    
                    # Cancel animation when we get the first response
                    animation_task.cancel()
                    
                    # Process the stream with timeout
                    async with asyncio.timeout(60):  # 60 second timeout
                        await self.bot.stream_handler.process_stream_with_updates(
                            thinking_msg, 
                            stream_generator,
                            self.bot.edit_message,
                            lambda msg, file: msg.edit(file=file)
                        )
                    grok_success = True
                    return  # If successful, return directly
                    
                except Exception as e:
                    error_str = str(e)
                    if "502" in error_str:
                        if attempt < max_retries - 1:
                            retry_wait = retry_delay * (2 ** attempt)  # Exponential backoff
                            try:
                                await thinking_msg.edit(f"Server error 502, retrying in {retry_wait} seconds... (attempt {attempt + 1}/{max_retries})")
                            except Exception as edit_error:
                                logger.error(f"Error editing message during retry: {edit_error}")
                            await asyncio.sleep(retry_wait)
                            continue
                        else:
                            # All retries have failed
                            try:
                                await thinking_msg.edit("Grok API is currently unavailable. Switching to DeepSeek model...")
                            except Exception as edit_error:
                                logger.error(f"Error editing message after all retries: {edit_error}")
                            break
                    elif "Content of the message was not modified" in error_str:
                        # If it's a message not modified error, try using the backup model
                        logger.info("Message not modified error detected. Switching to DeepSeek model...")
                        try:
                            await thinking_msg.edit("Message update error. Switching to DeepSeek model...")
                        except Exception as edit_error:
                            logger.error(f"Error editing message for model switch: {edit_error}")
                        break
                    else:
                        error_msg = f"Sorry, an error occurred: {str(e)}"
                        await self.bot.safe_send_message(thinking_msg, error_msg, event=event)
                        error_occurred = True
                        break
            
            # If Grok API failed, try using backup model
            if not grok_success:
                try:
                    # Use DeepSeek as a backup model
                    model = "deepseek-coder-33b-instruct"
                    stream_generator = llm_client.call_llm_stream('deepseek', prompt, model=model, mode="reasoner")
                    
                    # Process streaming response
                    await self.bot.stream_handler.process_stream_with_updates(
                        thinking_msg, 
                        stream_generator,
                        self.bot.edit_message,
                        lambda msg, file: msg.edit(file=file)
                    )
                    return
                    
                except Exception as e:
                    error_msg = f"Both Grok API and DeepSeek model failed. Error: {str(e)}"
                    await self.bot.safe_send_message(thinking_msg, error_msg, event=event)
                    error_occurred = True
                    
        except FloodWaitError as e:
            wait_seconds = e.seconds
            logger.warning(f"FloodWaitError when updating response: {wait_seconds} seconds wait required")
            
            error_msg = f"Response was generated but Telegram rate limits were hit. Please try again in {wait_seconds} seconds."
            await self.bot.safe_send_message(thinking_msg, error_msg, event=event)
            error_occurred = True
                
        except Exception as e:
            error_msg = f"Sorry, an error occurred: {str(e)}"
            await self.bot.safe_send_message(thinking_msg, error_msg, event=event)
            error_occurred = True
                
            logger.error(f"Error in grok3_stream_handler: {str(e)}")
            
        if error_occurred:
            # Provide additional information about the error
            try:
                await asyncio.sleep(1)  # Small delay before sending additional info
            except Exception as e:
                logger.error(f"Error sending additional error information: {str(e)}")
    
    async def _show_limited_thinking_animation(self, message, max_updates=5, interval=15):
        """
        Show a limited thinking animation
        
        Args:
            message: Message object
            max_updates: Maximum number of updates
            interval: Update interval (seconds)
        """
        from utils.animations import THINKING_ANIMATIONS
        
        for i in range(max_updates):
            try:
                dots = (i % 3) + 1
                thinking_text = "Thinking" + "." * dots + "\n\n"
                
                current_frame = thinking_text + THINKING_ANIMATIONS[i % len(THINKING_ANIMATIONS)]
                await message.edit(current_frame)
                
                await asyncio.sleep(interval)
            except FloodWaitError as e:
                logger.warning(f"FloodWaitError in limited animation: waiting {e.seconds} seconds")
                await asyncio.sleep(e.seconds + 5)
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error(f"Error in limited thinking animation: {str(e)}")