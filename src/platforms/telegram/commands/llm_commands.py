import asyncio
import logging
from telethon import events
from telethon.errors.rpcerrorlist import FloodWaitError
from .base import CommandHandler
from .utils import MessageHelper
from utils.animations import animated_thinking, INITIAL_MESSAGE_ART, SIMPLE_INITIAL_MESSAGE

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
            # Send initial response message
            response_message = await event.respond("Processing, please wait...")
            
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
                # Get appropriate stream generator based on LLM type
                stream_generator = self.llm_client.call_llm_stream(llm_type, prompt, model=model, system_prompt=system_prompt)
                
                # Process stream and update message
                await MessageHelper.process_stream_with_updates(
                    message_obj=response_message, 
                    stream_generator=stream_generator
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
        Handle Grok3 stream request
        
        Args:
            event: Telegram event object
            prompt: Prompt text
        """
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
            # Check if environment is test environment
            if self.llm_client.environment.lower() == 'test':
                test_task = asyncio.create_task(asyncio.to_thread(self.llm_client.call_test, prompt))
                response = await animated_thinking(thinking_msg, test_task)
                await MessageHelper.safe_send_message(thinking_msg, response)
                return
            
            # Check if Grok API key is available
            grok_provider_available = False
            if hasattr(self.llm_client, 'providers') and 'grok' in self.llm_client.providers:
                grok_provider = self.llm_client.providers['grok']
                if grok_provider and hasattr(grok_provider, 'api_key') and grok_provider.api_key:
                    grok_provider_available = True
                
            if not grok_provider_available:
                error_msg = "Grok API key not found. Please set GROK_API_KEY in your environment variables or credentials file."
                await MessageHelper.safe_send_message(thinking_msg, error_msg, event=event)
                return
                
            model = "grok-3-reasoner"
            system_prompt = "You are a helpful AI assistant with reasoning capabilities. Think through problems step by step and explore different aspects of the question. Format your response clearly with proper spacing, line breaks, and structure. Use markdown-style formatting like *bold*, _italic_, and `code` for emphasis. Use numbered lists (1., 2., 3.) and bullet points (- or *) for lists. Ensure your response is well-structured and easy to read."
            
            # Start animation
            from .utils import show_thinking_animation
            thinking_frames = [
                "Thinking.",
                "Thinking..",
                "Thinking...",
                "Thinking....",
            ]
            animation_task = asyncio.create_task(show_thinking_animation(thinking_msg, thinking_frames))
            
            # Try using Grok API
            grok_success = False
            for attempt in range(max_retries):
                try:
                    # Show attempt count
                    if attempt > 0:
                        try:
                            await thinking_msg.edit(f"Grok API request in progress... (attempt {attempt + 1}/{max_retries})")
                        except:
                            pass  # Ignore edit errors
                    
                    # Set timeout for API call
                    stream_generator = self.llm_client.call_grok3_stream(system_prompt, prompt, model_name=model)
                    
                    # Cancel animation when we get the first response
                    animation_task.cancel()
                    
                    # Process stream with timeout
                    async with asyncio.timeout(180):  # Increased to 180 seconds timeout
                        await MessageHelper.process_stream_with_updates(thinking_msg, stream_generator)
                    grok_success = True
                    return  # If successful, return directly
                    
                except asyncio.TimeoutError:
                    error_str = "Request timed out, possibly due to high server load"
                    if attempt < max_retries - 1:
                        retry_wait = retry_delay * (2 ** attempt)  # Exponential backoff
                        try:
                            await thinking_msg.edit(f"API request timed out, retrying in {retry_wait} seconds... (attempt {attempt + 1}/{max_retries})")
                        except Exception as edit_error:
                            logger.error(f"Error editing message during retry: {edit_error}")
                        await asyncio.sleep(retry_wait)
                        continue
                    else:
                        try:
                            await thinking_msg.edit("Grok API request timed out multiple times, switching to DeepSeek model...")
                        except:
                            pass
                        break
                        
                except Exception as e:
                    error_str = str(e)
                    if "timed out" in error_str.lower() or "timeout" in error_str.lower() or "502" in error_str:
                        if attempt < max_retries - 1:
                            retry_wait = retry_delay * (2 ** attempt)  # Exponential backoff
                            try:
                                await thinking_msg.edit(f"Connection error, retrying in {retry_wait} seconds... (attempt {attempt + 1}/{max_retries})")
                            except Exception as edit_error:
                                logger.error(f"Error editing message during retry: {edit_error}")
                            await asyncio.sleep(retry_wait)
                            continue
                        else:
                            # All retries have failed
                            try:
                                await thinking_msg.edit("Grok API currently unavailable, switching to DeepSeek model...")
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
                        await MessageHelper.safe_send_message(thinking_msg, error_msg, event=event)
                        error_occurred = True
                        break
            
            # If Grok API failed, try using backup model
            if not grok_success:
                try:
                    # Use DeepSeek as backup model
                    model = "deepseek-coder-33b-instruct"
                    stream_generator = self.llm_client.call_deepseek_stream(prompt, model=model, mode="reasoner")
                    
                    # Show message that we're using the backup model
                    try:
                        await thinking_msg.edit("Using DeepSeek model to process request...")
                    except:
                        pass
                    
                    # Process streaming response
                    await MessageHelper.process_stream_with_updates(thinking_msg, stream_generator)
                    return
                    
                except Exception as e:
                    error_msg = f"Both Grok API and DeepSeek model failed. Error: {str(e)}"
                    await MessageHelper.safe_send_message(thinking_msg, error_msg, event=event)
                    error_occurred = True
                
        except FloodWaitError as e:
            wait_seconds = e.seconds
            logger.warning(f"FloodWaitError when updating response: {wait_seconds} seconds wait required")
            
            error_msg = f"Response was generated but Telegram rate limits were hit. Please try again in {wait_seconds} seconds."
            await MessageHelper.safe_send_message(thinking_msg, error_msg, event=event)
            error_occurred = True
                
        except Exception as e:
            # error_msg = f"Sorry, an error occurred: {str(e)}"
            # await MessageHelper.safe_send_message(thinking_msg, error_msg, event=event)
            error_occurred = True
                
            logger.error(f"Error in grok3_stream_handler: {str(e)}")
            
        if error_occurred:
                logger.error(f"Error sending additional error information: {str(e)}")
    
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