import asyncio
import io
import os
import time
import logging
from telethon.errors.rpcerrorlist import FloodWaitError

logger = logging.getLogger("telegram_commands_utils")

class MessageHelper:
    """
    Utility class for handling Telegram messages
    """
    
    @staticmethod
    async def safe_send_message(message_obj, text, event=None, parse_mode=None):
        """
        Safely send a message, handling long messages and errors
        
        Args:
            message_obj: Message object to edit
            text (str): Text to send
            event: Original event object (for fallback)
            parse_mode: Text parsing mode
            
        Returns:
            bool: True if successfully sent
        """
        TELEGRAM_MAX_LENGTH = 4000
        max_retry_times = 2  # Maximum retry times
        
        # Check if text is a file path
        if isinstance(text, str) and text.startswith("logs/") and os.path.exists(text):
            try:
                # Directly send file path
                await message_obj.edit(file=text)
                return True
            except FloodWaitError as e:
                wait_seconds = e.seconds
                logger.warning(f"FloodWaitError in safe_send_message (file path): {wait_seconds}s wait required")
                
                # If wait time isn't too long, wait and retry
                if wait_seconds <= 180:  # Maximum wait of 3 minutes
                    try:
                        logger.info(f"Waiting {wait_seconds} seconds before retry...")
                        await asyncio.sleep(wait_seconds + 1)  # Wait an extra second to ensure safety
                        await message_obj.edit(file=text)
                        return True
                    except Exception as retry_e:
                        logger.error(f"Retry failed after waiting: {retry_e}")
                
                # Try to read file content and send as memory file
                try:
                    with open(text, "rb") as f:
                        file_content = f.read()
                    file_obj = io.BytesIO(file_content)
                    file_obj.name = os.path.basename(text)
                    
                    # Wait again to avoid triggering rate limits
                    await asyncio.sleep(2)
                    await message_obj.edit(file=file_obj)
                    return True
                except FloodWaitError as e2:
                    logger.error(f"Second FloodWaitError: {e2.seconds}s wait required. Giving up.")
                    return False
                except Exception as e2:
                    logger.error(f"Error sending file from memory after reading {text}: {e2}")
                    # Continue with normal processing, try to send text
        
        # Handle normal text
        if len(text) > TELEGRAM_MAX_LENGTH:
            try:
                # Create temporary file in memory instead of on disk
                file_obj = io.BytesIO(text.encode('utf-8'))
                file_obj.name = "output.txt"
                
                # Edit message to send file
                await message_obj.edit(file=file_obj)
                return True
            except FloodWaitError as e:
                wait_seconds = e.seconds
                logger.warning(f"FloodWaitError in safe_send_message (memory file): {wait_seconds}s wait required")
                
                # If wait time isn't too long, wait and retry
                if wait_seconds <= 180:  # Maximum wait of 3 minutes
                    try:
                        logger.info(f"Waiting {wait_seconds} seconds before retry...")
                        await asyncio.sleep(wait_seconds + 1)
                        await message_obj.edit(file=file_obj)
                        return True
                    except Exception as retry_e:
                        logger.error(f"Failed to edit message after waiting: {retry_e}")
                
                # If still failing, try to save to disk and send the file
                try:
                    if not os.path.exists('logs'):
                        os.makedirs('logs')
                    
                    file_path = "logs/output.txt"
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(text)
                    
                    # Wait again to avoid triggering rate limits
                    await asyncio.sleep(2)
                    await message_obj.edit(file=file_path)
                    return True
                except Exception as file_e:
                    logger.error(f"Error sending disk file: {file_e}")
                
                # If all attempts fail, only send truncated message as last resort
                if event is not None:
                    for retry in range(max_retry_times):
                        try:
                            truncated_msg = text[:TELEGRAM_MAX_LENGTH - 100] + "...\n\n[Message too long, truncated]"
                            await event.respond(truncated_msg)
                            return True
                        except FloodWaitError as respond_e:
                            # If this is the last retry, give up
                            if retry == max_retry_times - 1:
                                logger.error(f"Final FloodWaitError: {respond_e.seconds}s required. Giving up.")
                                return False
                            
                            # Otherwise wait and retry
                            wait_time = respond_e.seconds
                            logger.info(f"FloodWaitError in respond: {wait_time}s required. Waiting...")
                            await asyncio.sleep(wait_time + 1)
                        except Exception as respond_error:
                            logger.error(f"Error sending reply message: {respond_error}")
                            break
                
                return False
            except Exception as e:
                logger.error(f"Error sending file: {e}")
                # Try to send new message as last resort
                if event is not None:
                    for retry in range(max_retry_times):
                        try:
                            truncated_msg = text[:TELEGRAM_MAX_LENGTH - 100] + "...\n\n[Message too long, truncated]"
                            await event.respond(truncated_msg)
                            return True
                        except FloodWaitError as respond_e:
                            # If this is the last retry, give up
                            if retry == max_retry_times - 1:
                                logger.error(f"Final FloodWaitError: {respond_e.seconds}s required. Giving up.")
                                return False
                            
                            # Otherwise wait and retry
                            wait_time = respond_e.seconds
                            logger.info(f"FloodWaitError in respond: {wait_time}s required. Waiting...")
                            await asyncio.sleep(wait_time + 1)
                        except Exception as respond_error:
                            logger.error(f"Error sending reply message: {respond_error}")
                            return False
                return False
        else:
            retry_count = 0
            while retry_count <= max_retry_times:
                try:
                    await message_obj.edit(text, parse_mode=parse_mode)
                    return True
                except FloodWaitError as e:
                    wait_seconds = e.seconds
                    logger.warning(f"FloodWaitError in safe_send_message: {wait_seconds}s wait required (retry {retry_count+1}/{max_retry_times+1})")
                    
                    # Last retry, if wait time is too long, give up
                    if retry_count == max_retry_times or wait_seconds > 180:
                        break
                    
                    # Otherwise wait and retry
                    try:
                        logger.info(f"Waiting {wait_seconds} seconds before retry...")
                        await asyncio.sleep(wait_seconds + 1)
                        retry_count += 1
                    except Exception as sleep_error:
                        logger.error(f"Error during sleep: {sleep_error}")
                        break
                
                except Exception as e:
                    error_str = str(e)
                    if "Content of the message was not modified" in error_str:
                        logger.info("Message not modified error in safe_send_message. This is usually harmless.")
                        return True  # Consider as success since content didn't change
                        
                    logger.error(f"Error in safe_send_message: {e}")
                    break
            
            # If editing original message fails, try sending a new message
            if event is not None:
                for retry in range(max_retry_times):
                    try:
                        await event.respond(text, parse_mode=parse_mode)
                        return True
                    except FloodWaitError as respond_e:
                        # If this is the last retry, give up
                        if retry == max_retry_times - 1:
                            logger.error(f"Final FloodWaitError: {respond_e.seconds}s required. Giving up.")
                            return False
                        
                        # Otherwise wait and retry
                        wait_time = respond_e.seconds
                        logger.info(f"FloodWaitError in respond: {wait_time}s required. Waiting...")
                        await asyncio.sleep(wait_time + 1)
                    except Exception as reply_e:
                        logger.error(f"Failed to send new message: {reply_e}")
                        if retry == max_retry_times - 1:
                            return False
                        # Continue to next retry
                        await asyncio.sleep(2)
            
            # If all attempts fail, return failure
            return False
    
    @staticmethod
    async def process_stream_with_updates(message_obj, stream_generator, min_update_interval=1.5):
        """
        Process streaming responses and update message
        
        Args:
            message_obj: Telegram message object to update
            stream_generator: Generator producing text chunks
            min_update_interval: Minimum interval between updates (seconds)
        """
        full_response = ""
        last_update_time = time.time()
        error_message = None
        max_retries = 3
        
        try:
            for chunk in stream_generator:
                if chunk is None:
                    continue
                    
                # Check if chunk contains error message
                if isinstance(chunk, str) and (chunk.startswith("Error:") or chunk.startswith("Sorry, an error occurred")):
                    error_message = chunk
                    break
                    
                # Add chunk to full response
                if isinstance(chunk, str):
                    full_response += chunk
                
                # Only update if enough time has passed since last update
                current_time = time.time()
                if current_time - last_update_time >= min_update_interval:
                    for retry in range(max_retries):
                        try:
                            # Check if response is too long for a single message
                            if len(full_response) > 4000:
                                # Create temporary file in memory
                                file_obj = io.BytesIO(full_response.encode('utf-8'))
                                file_obj.name = "response.txt"
                                
                                # Edit message to send file
                                await message_obj.edit(file=file_obj)
                            else:
                                await message_obj.edit(full_response)
                                
                            last_update_time = current_time
                            break
                        except FloodWaitError as e:
                            logger.warning(f"FloodWaitError in stream update: {e.seconds}s wait required (retry {retry+1}/{max_retries})")
                            if retry < max_retries - 1:
                                await asyncio.sleep(e.seconds + 1)
                            else:
                                logger.error("Max retries reached for stream update")
                        except Exception as e:
                            if "not modified" not in str(e).lower():
                                logger.error(f"Error updating message in stream: {e}")
                                if retry < max_retries - 1:
                                    await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Error in process_stream_with_updates: {e}")
            error_message = f"Error processing stream: {str(e)}"
        
        # Handle final response
        if error_message:
            for retry in range(max_retries):
                try:
                    await message_obj.edit(error_message)
                    break
                except Exception as e:
                    logger.error(f"Error sending error message (retry {retry+1}/{max_retries}): {e}")
                    if retry < max_retries - 1:
                        await asyncio.sleep(1)
        elif full_response:
            for retry in range(max_retries):
                try:
                    # Check if response is too long for a single message
                    if len(full_response) > 4000:
                        # Create temporary file in memory
                        file_obj = io.BytesIO(full_response.encode('utf-8'))
                        file_obj.name = "response.txt"
                        
                        # Edit message to send file
                        await message_obj.edit(file=file_obj)
                    else:
                        await message_obj.edit(full_response)
                    break
                except Exception as e:
                    logger.error(f"Error sending final response (retry {retry+1}/{max_retries}): {e}")
                    if retry < max_retries - 1:
                        await asyncio.sleep(1)
        else:
            for retry in range(max_retries):
                try:
                    await message_obj.edit("No response received from API.")
                    break
                except Exception as e:
                    logger.error(f"Error sending no response message (retry {retry+1}/{max_retries}): {e}")
                    if retry < max_retries - 1:
                        await asyncio.sleep(1)

class FloodWaitHandler:
    """
    Helper class for handling Telegram FloodWait errors
    """
    def __init__(self):
        self.last_edit_time = {}
        self.min_edit_interval = 1.5
    
    async def safe_edit_message(self, message, text):
        """
        Safely edit a message, handling FloodWaitError
        
        Args:
            message: Message object to edit
            text: New message text
            
        Returns:
            bool: True for success, False for failure
        """
        message_id = f"{message.chat_id}:{message.id}"
        current_time = time.time()
        max_retries = 3
        
        if message_id in self.last_edit_time:
            elapsed = current_time - self.last_edit_time[message_id]
            if elapsed < self.min_edit_interval:
                await asyncio.sleep(self.min_edit_interval - elapsed)
        
        for retry in range(max_retries):
            try:
                await message.edit(text)
                self.last_edit_time[message_id] = time.time()
                return True
            
            except FloodWaitError as e:
                wait_seconds = getattr(e, 'seconds', 60)
                
                if retry < max_retries - 1:
                    logger.info(f"FloodWaitError: Waiting for {wait_seconds} seconds before retrying (retry {retry+1}/{max_retries})")
                    await asyncio.sleep(wait_seconds + 1)
                else:
                    logger.warning(f"FloodWaitError with long wait time ({wait_seconds} seconds). Max retries reached.")
                    return False
                
            except Exception as e:
                logger.error(f"Error editing message (retry {retry+1}/{max_retries}): {str(e)}")
                if retry < max_retries - 1:
                    await asyncio.sleep(1)
                else:
                    return False
        
        return False

async def show_thinking_animation(message, frames, max_updates=5, interval=3):
    """
    Show thinking animation on a message
    
    Args:
        message: Message object to animate
        frames: List of animation frames
        max_updates: Maximum animation updates
        interval: Seconds between updates
    """
    try:
        for i in range(max_updates):
            frame = frames[i % len(frames)]
            try:
                await message.edit(frame)
            except FloodWaitError as e:
                logger.warning(f"FloodWaitError in thinking animation: {e.seconds}s wait required")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                if "not modified" not in str(e).lower():
                    logger.error(f"Error updating thinking animation: {e}")
            
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        # Animation was cancelled, this is normal
        return
    except Exception as e:
        logger.error(f"Error in thinking animation: {e}")