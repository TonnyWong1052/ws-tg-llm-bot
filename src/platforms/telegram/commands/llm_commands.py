import asyncio
import logging
from telethon import events
from telethon.errors.rpcerrorlist import FloodWaitError
from .base import CommandHandler
from .utils import MessageHelper
from utils.animations import animated_thinking, INITIAL_MESSAGE_ART, SIMPLE_INITIAL_MESSAGE, THINKING_ANIMATIONS
import time
import os

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
            if not self.client.llm_client:
                await response_message.edit("LLM client not initialized, cannot process request.")
                return
            
            model = model_name if model_name else provider
            
            # Get appropriate stream generator based on provider
            stream_generator = self.client.llm_client.call_llm_stream(provider, prompt, model=model)
            
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
    
    async def _process_llm_request(self, llm_type, prompt, model, system_prompt, response_message):
        """
        Process LLM request asynchronously
        
        Args:
            llm_type: LLM type
            prompt: Prompt text
            model: Model name
            system_prompt: System prompt
            response_message: Response message object
        """
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
            
        except Exception as e:
            logger.error(f"Error in _process_llm_request: {e}")
            await response_message.edit(f"Error occurred: {str(e)}")
    
    async def deepseek_handler(self, event):
        """Handle the /deepseek command"""
        # Create a unique task ID for this command execution
        task_id = f"deepseek_{event.id}_{int(time.time())}"
        
        # Create a task for command processing
        task = asyncio.create_task(self._process_deepseek(event))
        
        # Store the task in the bot's handlers dictionary with the unique task ID
        self.client.handlers[task_id] = task
        
        # Add task to active tasks set
        self.client.active_tasks.add(task)
        task.add_done_callback(self.client.active_tasks.discard)
        task.add_done_callback(lambda t: self.client.handlers.pop(task_id, None))
    
    async def r1_handler(self, event):
        """Handle the /r1 command"""
        task_id = f"r1_{event.id}_{int(time.time())}"
        task = asyncio.create_task(self._process_r1(event))
        self.client.handlers[task_id] = task
        self.client.active_tasks.add(task)
        task.add_done_callback(self.client.active_tasks.discard)
        task.add_done_callback(lambda t: self.client.handlers.pop(task_id, None))

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

    async def _process_r1(self, event):
        """Process R1 command asynchronously"""
        try:
            # Get prompt from message
            prompt = event.pattern_match.group(1).strip()
            
            # If prompt is empty, return help message
            if not prompt:
                await event.reply("Please provide content to process: /r1 your question or request")
                return
            
            # Send initial response message with animation
            response_message = await event.respond(INITIAL_MESSAGE_ART)
            
            # Store message in task_messages
            task_id = f"r1_{event.id}_{int(time.time())}"
            self.client.task_messages[task_id] = response_message
            self.client.task_start_times[task_id] = time.time()
            
            # Create an async generator for the stream
            async def stream_generator():
                # Get stream generator
                sync_generator = self.client.llm_client.call_llm_stream(
                    'deepseek', 
                    prompt, 
                    model="deepseek-reasoner",
                    system_prompt="You are a helpful AI assistant with strong reasoning capabilities. Think through problems step by step and provide detailed, logical explanations with clear reasoning chains."
                )
                
                # Convert sync generator to async
                for chunk in sync_generator:
                    if chunk:
                        yield chunk
                    # Small delay to allow other coroutines to run
                    await asyncio.sleep(0)
            
            # Process stream and update message
            current_text = ""
            async for chunk in stream_generator():
                try:
                    current_text += chunk
                    # Update message if it's significantly different
                    if len(current_text) % 50 == 0:  # Update every 50 chars
                        await response_message.edit(current_text)
                        await asyncio.sleep(0.1)  # Small delay to prevent rate limiting
                        
                except FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                    continue
                except Exception as e:
                    logger.error(f"Error updating message: {e}")
                    continue
            
            # Final update to ensure we don't miss the last chunk
            if current_text:
                try:
                    await response_message.edit(current_text)
                except Exception as e:
                    logger.error(f"Error in final message update: {e}")
            
        except FloodWaitError as e:
            await self.handle_flood_wait_error(event, e)
        except Exception as e:
            logger.error(f"Error in _process_r1: {e}")
            import traceback
            traceback.print_exc()
            await self.handle_error(event, e)

    async def _process_deepseek(self, event):
        """Process deepseek command asynchronously"""
        try:
            # Get prompt from message
            prompt = event.pattern_match.group(1).strip()
            
            # If prompt is empty, return help message
            if not prompt:
                await event.reply("Please provide content to process: /deepseek your question or request")
                return
            
            # Send initial response message with animation
            response_message = await event.respond(INITIAL_MESSAGE_ART)
            
            # Store message in task_messages
            task_id = f"deepseek_{event.id}_{int(time.time())}"
            self.client.task_messages[task_id] = response_message
            self.client.task_start_times[task_id] = time.time()
            
            # Create an async generator for the stream
            async def stream_generator():
                # Get stream generator
                sync_generator = self.client.llm_client.call_llm_stream(
                    'deepseek', 
                    prompt, 
                    model="deepseek-reasoner",
                    system_prompt="You are a helpful AI assistant called DeepSeek. Always provide clear, detailed and accurate responses."
                )
                
                # Convert sync generator to async
                for chunk in sync_generator:
                    if chunk:
                        yield chunk
                    # Small delay to allow other coroutines to run
                    await asyncio.sleep(0)
            
            # Process stream and update message
            current_text = ""
            async for chunk in stream_generator():
                try:
                    current_text += chunk
                    # Update message if it's significantly different
                    if len(current_text) % 50 == 0:  # Update every 50 chars
                        await response_message.edit(current_text)
                        await asyncio.sleep(0.1)  # Small delay to prevent rate limiting
                        
                except FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                    continue
                except Exception as e:
                    logger.error(f"Error updating message: {e}")
                    continue
            
            # Final update to ensure we don't miss the last chunk
            if current_text:
                try:
                    await response_message.edit(current_text)
                except Exception as e:
                    logger.error(f"Error in final message update: {e}")
            
        except FloodWaitError as e:
            await self.handle_flood_wait_error(event, e)
        except Exception as e:
            logger.error(f"Error in _process_deepseek: {e}")
            import traceback
            traceback.print_exc()
            await self.handle_error(event, e)

    async def env_handler(self, event):
        """Handle the /env command"""
        try:
            # Get environment information
            import sys
            import platform
            
            env_info = [
                f"Python version: {sys.version}",
                f"Platform: {platform.platform()}",
                f"Working directory: {os.getcwd()}",
                f"Environment variables: {len(os.environ)} variables set"
            ]
            
            await event.reply("\n".join(env_info))
        except Exception as e:
            await self.handle_error(event, e)

    async def ping_handler(self, event):
        """Handle the /ping command"""
        try:
            import time
            start_time = time.time()
            message = await event.reply("Pong!")
            end_time = time.time()
            
            # Calculate round trip time
            rtt = (end_time - start_time) * 1000  # Convert to milliseconds
            
            await message.edit(f"Pong! RTT: {rtt:.2f}ms")
        except Exception as e:
            await self.handle_error(event, e)

    async def gpt_handler(self, event):
        """Handle the /gpt command"""
        task_id = f"gpt_{event.id}_{int(time.time())}"
        task = asyncio.create_task(self._process_gpt(event))
        self.client.handlers[task_id] = task
        self.client.active_tasks.add(task)
        task.add_done_callback(self.client.active_tasks.discard)
        task.add_done_callback(lambda t: self.client.handlers.pop(task_id, None))

    async def _process_gpt(self, event):
        """Process GPT command asynchronously"""
        try:
            # Get prompt from message
            prompt = event.pattern_match.group(1).strip()
            
            # If prompt is empty, return help message
            if not prompt:
                await event.reply("Please provide content to process: /gpt your question or request")
                return
            
            # Send initial response message with animation
            response_message = await event.respond(INITIAL_MESSAGE_ART)
            
            # Store message in task_messages
            task_id = f"gpt_{event.id}_{int(time.time())}"
            self.client.task_messages[task_id] = response_message
            self.client.task_start_times[task_id] = time.time()
            
            # Create an async generator for the stream
            async def stream_generator():
                # Get stream generator using GitHub API
                sync_generator = self.client.llm_client.call_llm_stream(
                    'openai', 
                    prompt, 
                    model="gpt-4.1",  # GitHub hosted model
                    system_prompt="You are GPT, a helpful AI assistant. Always provide clear, detailed and accurate responses."
                )
                
                # Convert sync generator to async
                for chunk in sync_generator:
                    if chunk:
                        yield chunk
                    # Small delay to allow other coroutines to run
                    await asyncio.sleep(0)
            
            # Process stream and update message
            current_text = ""
            async for chunk in stream_generator():
                try:
                    current_text += chunk
                    # Update message if it's significantly different
                    if len(current_text) % 50 == 0:  # Update every 50 chars
                        await response_message.edit(current_text)
                        await asyncio.sleep(0.1)  # Small delay to prevent rate limiting
                        
                except FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                    continue
                except Exception as e:
                    logger.error(f"Error updating message: {e}")
                    continue
            
            # Final update to ensure we don't miss the last chunk
            if current_text:
                try:
                    await response_message.edit(current_text)
                except Exception as e:
                    logger.error(f"Error in final message update: {e}")
            
        except FloodWaitError as e:
            await self.handle_flood_wait_error(event, e)
        except Exception as e:
            logger.error(f"Error in _process_gpt: {e}")
            import traceback
            traceback.print_exc()
            await self.handle_error(event, e)