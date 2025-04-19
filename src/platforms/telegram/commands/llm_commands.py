import asyncio
import logging
from telethon import events
from telethon.errors.rpcerrorlist import FloodWaitError
from .base import CommandHandler
from .utils import MessageHelper
from utils.animations import animated_thinking, INITIAL_MESSAGE_ART, SIMPLE_INITIAL_MESSAGE, THINKING_ANIMATIONS

logger = logging.getLogger("telegram_llm_commands")

class LLMCommandHandler(CommandHandler):
    """
    Handler class for LLM-related commands
    """
    
    def __init__(self, client, llm_client):
        """
        Initialize LLM command handler
        
        Args:
            client: Telegram client
            llm_client: LLM client instance
        """
        super().__init__(client, llm_client)
        
    async def register_handlers(self):
        """
        Register all LLM-related command handlers
        """
        self.client.add_event_handler(
            self.deepseek_handler,
            events.NewMessage(pattern=r'/deepseek\s*(.*)')
        )
        
        self.client.add_event_handler(
            self.r1_handler,
            events.NewMessage(pattern=r'/r1\s*(.*)')
        )
        
        self.client.add_event_handler(
            self.gpt_handler,
            events.NewMessage(pattern=r'/gpt\s*(.*)')
        )
        
        self.client.add_event_handler(
            self.grok_handler,
            events.NewMessage(pattern=r'/grok\s*(.*)')
        )
        
        self.client.add_event_handler(
            self.grok_think_handler,
            events.NewMessage(pattern=r'^/grok_think (.+)')
        )
        
        logger.info("LLM command handlers registered")
    
    async def handle_llm_request(self, event, llm_type, prompt, model_name=None, system_prompt=None, display_name=None):
        """
        Handle LLM request
        
        Args:
            event: Telegram event object
            llm_type: LLM type ('deepseek', 'grok', etc.)
            prompt: Prompt text
            model_name: Model name (optional)
            system_prompt: System prompt (optional)
            display_name: Display name (optional)
        """
        response_message = None
        
        try:
            # Send initial response message with animation
            try:
                response_message = await event.respond(INITIAL_MESSAGE_ART)
            except FloodWaitError as e:
                logger.warning(f"FloodWaitError with art message: {e.seconds} seconds wait required. Using simple message instead.")
                await asyncio.sleep(2)
                response_message = await event.respond("Thinking...")
            except Exception as e:
                logger.error(f"Error sending initial message: {e}. Using simple message instead.")
                response_message = await event.respond("Thinking...")
            
            # Ensure LLM client is initialized
            if not self.llm_client:
                await response_message.edit("LLM client not initialized, cannot process request.")
                return
            
            # Log information about available providers
            logger.info(f"Available LLM providers: {list(self.llm_client.providers.keys()) if hasattr(self.llm_client, 'providers') else 'No providers'}")
            
            # Check if the requested provider is available
            if hasattr(self.llm_client, 'providers') and llm_type not in self.llm_client.providers:
                await response_message.edit(f"Provider '{llm_type}' is not available. Available providers: {list(self.llm_client.providers.keys())}")
                return
            
            model = model_name if model_name else llm_type
            
            logger.info(f"Calling {llm_type} with prompt: {prompt[:50]}...")
            
            try:
                # Get stream generator
                stream_generator = self.llm_client.call_llm_stream(llm_type, prompt, model=model, system_prompt=system_prompt)
                
                # Process stream and update message
                await MessageHelper.process_stream_with_updates(
                    message_obj=response_message,
                    stream_generator=stream_generator,
                    min_update_interval=0
                )
                
            except AttributeError as e:
                # Fall back to non-streaming method if streaming is not available
                logger.warning(f"Streaming not available for {llm_type}, falling back to non-streaming method: {e}")
                response = self.llm_client.call_llm(llm_type, prompt, model=model, system_prompt=system_prompt)
                await MessageHelper.safe_send_message(response_message, response)
            
        except FloodWaitError as e:
            await self.handle_flood_wait_error(event, e, response_message)
            
        except Exception as e:
            logger.error(f"Error in handle_llm_request: {e}")
            import traceback
            traceback.print_exc()
            
            # Try to send error message
            await self.handle_error(event, e, response_message)
    
    async def deepseek_handler(self, event):
        """DeepSeek command handler"""
        # Get prompt from message
        prompt = event.pattern_match.group(1).strip()
        
        # If prompt is empty, return help message
        if not prompt:
            await event.reply("Please provide content to process: /deepseek your question or request")
            return
        
        # Use handle_llm_request for processing
        system_prompt = "You are DeepSeek Coder, a helpful coding assistant. Always provide clear and concise responses."
        await self.handle_llm_request(
            event, 
            'deepseek', 
            prompt, 
            model_name="deepseek-coder-33b-instruct", 
            system_prompt=system_prompt, 
            display_name="DeepSeek Coder"
        )
    
    async def r1_handler(self, event):
        """R1 command handler that uses the deepseek-reasoner model"""
        # Get prompt from message
        prompt = event.pattern_match.group(1).strip()
        
        # If prompt is empty, return help message
        if not prompt:
            await event.reply("Please provide content to process: /r1 your question or request")
            return
        
        # Use handle_llm_request for processing
        system_prompt = "You are a helpful AI assistant with strong reasoning capabilities. Think through problems step by step and provide detailed, logical explanations with clear reasoning chains."
        await self.handle_llm_request(
            event, 
            'deepseek', 
            prompt, 
            model_name="deepseek-reasoner",
            system_prompt=system_prompt, 
            display_name="R1 Reasoner"
        )
    
    async def gpt_handler(self, event):
        """GPT command handler"""
        # Get prompt from message
        prompt = event.pattern_match.group(1).strip()
        
        # If prompt is empty, return help message
        if not prompt:
            await event.reply("Please provide content to process: /gpt your question or request")
            return
        
        # Use handle_llm_request for processing
        system_prompt = "You are a helpful AI assistant called GPT. Always provide clear and comprehensive responses."
        await self.handle_llm_request(
            event, 
            'openai',  # Changed from 'gpt' to 'openai' to match the available provider
            prompt, 
            system_prompt=system_prompt, 
            model_name="gpt-4o-mini",
            display_name="GPT"
        )
    
    async def grok_handler(self, event):
        """Grok command handler"""
        # Get prompt from message
        prompt = event.pattern_match.group(1).strip()
        
        # If prompt is empty, return help message
        if not prompt:
            await event.reply("Please provide content to process: /grok your question or request")
            return
        
        # Use handle_llm_request for processing
        system_prompt = "You are a helpful AI assistant called Grok. Always provide clear, detailed and accurate responses."
        await self.handle_llm_request(
            event, 
            'grok', 
            prompt, 
            system_prompt=system_prompt, 
            model_name="grok-3",
            display_name="Grok"
        )
        
    async def grok_think_handler(self, event):
        """Grok thinking mode handler"""
        try:
            # Get prompt
            prompt = event.pattern_match.group(1).strip()
            
            # If prompt is empty, return help message
            if not prompt:
                await event.reply("Please provide content to process: /grok_think your question or request")
                return
                
            await self.handle_grok3_stream_request(event, prompt)
        except FloodWaitError as e:
            # Directly handle top-level FloodWaitError
            await self.handle_flood_wait_error(event, e)
        except Exception as e:
            logger.error(f"Unhandled exception in grok_think_handler: {e}")
            import traceback
            traceback.print_exc()
            
            # Send error message
            await self.handle_error(event, e)
            
    async def handle_grok3_stream_request(self, event, prompt):
        """
        Handle streaming request to Grok-3 API
        
        Args:
            event: Telegram event object
            prompt: User prompt
        """
        response_message = None
        max_retries = 3
        
        try:
            # Send initial response message with animation
            try:
                response_message = await event.respond(INITIAL_MESSAGE_ART)
            except FloodWaitError as e:
                logger.warning(f"FloodWaitError with art message: {e.seconds} seconds wait required. Using simple message instead.")
                await asyncio.sleep(2)
                response_message = await event.respond("Thinking...")
            except Exception as e:
                logger.error(f"Error sending initial message: {e}. Using simple message instead.")
                response_message = await event.respond("Thinking...")
            
            # Create task for LLM call
            llm_task = asyncio.create_task(
                self.llm_client.call_llm_stream('grok', prompt, model='grok-3')
            )
            
            # Start animation and wait for LLM response
            response = await animated_thinking(response_message, llm_task)
            
            # Process the response
            if isinstance(response, str):
                await MessageHelper.process_stream_with_updates(
                    message_obj=response_message,
                    stream_generator=[response],
                    min_update_interval=0
                )
            else:
                await MessageHelper.process_stream_with_updates(
                    message_obj=response_message,
                    stream_generator=response,
                    min_update_interval=0
                )
            
        except FloodWaitError as e:
            await self.handle_flood_wait_error(event, e, response_message)
            
        except Exception as error:
            logger.error(f"Error in handle_grok3_stream_request: {error}")
            import traceback
            logger.error(traceback.format_exc())
            
            # Try to send error message
            try:
                if response_message:
                    await response_message.edit(f"Error occurred: {str(error)}")
                else:
                    await event.respond(f"Error occurred: {str(error)}")
            except Exception as send_error:
                logger.error(f"Error sending error message: {send_error}")
                try:
                    # Try to send additional error information
                    await event.respond(f"Additional error information: {str(send_error)}")
                except Exception as additional_error:
                    logger.error(f"Error sending additional error information: {str(additional_error)}")
    
    async def handle_flood_wait_error(self, event, e, response_message=None):
        """
        Handle FloodWaitError error
        
        Args:
            event: Triggering event
            e: FloodWaitError exception
            response_message: Response message object (optional)
        """
        wait_seconds = e.seconds
        logger.warning(f"FloodWaitError in handle_llm_request: {wait_seconds}s wait required")
        
        try:
            if response_message:
                await response_message.edit(f"Telegram rate limit triggered, need to wait {wait_seconds} seconds. Please try again later.")
            else:
                await event.respond(f"Telegram rate limit triggered, need to wait {wait_seconds} seconds. Please try again later.")
        except Exception as edit_error:
            logger.error(f"Unable to edit/send rate limit message: {edit_error}")
            
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
            logger.error(f"Unable to send error message: {reply_error}")