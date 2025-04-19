import asyncio
import io
import logging
from abc import ABC, abstractmethod

class MessageHandler(ABC):
    """
    Unified message handling base class that provides cross-platform message handling functionality
    """
    def __init__(self, bot):
        """
        Initialize the message handler
        
        Args:
            bot: Bot instance
        """
        self.bot = bot
        self.logger = logging.getLogger(f"{bot.platform}_message_handler")
    
    @abstractmethod
    async def handle_message(self, message, **kwargs):
        """
        Handle received messages
        
        Args:
            message: Received message object
            **kwargs: Additional platform-specific parameters
        """
        pass
    
    @abstractmethod
    async def handle_command(self, command, message, **kwargs):
        """
        Handle command messages
        
        Args:
            command (str): Command name
            message: Message object
            **kwargs: Additional platform-specific parameters
        """
        pass


class StreamHandler:
    """
    Generic stream response handler class
    """
    def __init__(self, max_length=4000):
        """
        Initialize the stream handler
        
        Args:
            max_length (int): Maximum message length
        """
        self.max_length = max_length
        self.logger = logging.getLogger("stream_handler")
    
    async def process_stream_with_updates(self, message, stream_generator, message_edit_func, send_file_func, min_update_interval=3.0, split_long_messages=True):
        """
        Process stream responses and update the message periodically
        
        Args:
            message: Message object
            stream_generator: Stream response generator
            message_edit_func: Function to edit the message
            send_file_func: Function to send a file
            min_update_interval (float): Minimum update interval (seconds)
            split_long_messages (bool): Whether to split long messages instead of sending as file
        """
        full_response = ""
        last_update_time = 0
        consecutive_errors = 0
        max_consecutive_errors = 3
        telegram_char_limit = 2500  # Character limit for Telegram message updates
        
        try:
            all_chunks = []
            error_occurred = False
            response_too_long = False
            message_not_modified_error = False
            last_successful_update = ""
            telegram_limit_exceeded = False
            
            self.logger.info(f"Starting stream processing with Telegram limit set to {telegram_char_limit} characters")
            
            # Process streaming content
            chunk_counter = 0
            async for chunk in self._async_generator_from_sync(stream_generator):
                chunk_counter += 1
                
                if isinstance(chunk, str) and (chunk.startswith("Error") or chunk.startswith("API returned error")):
                    error_message = f"Sorry, there was an issue with the API: {chunk}"
                    await message_edit_func(message, error_message)
                    error_occurred = True
                    self.logger.error(f"API error received: {chunk}")
                    break
                
                all_chunks.append(chunk)
                full_response = chunk
                current_length = len(full_response)
                
                if chunk_counter % 5 == 0 or current_length > telegram_char_limit - 500:
                    self.logger.debug(f"Chunk #{chunk_counter}: Current response length is {current_length} characters")
                
                # Check if response is too long for general limit
                if current_length > self.max_length:
                    response_too_long = True
                    self.logger.debug(f"Response exceeds max length ({self.max_length}): {current_length}")
                
                # Check if response exceeds Telegram limit
                if current_length > telegram_char_limit:
                    telegram_limit_exceeded = True
                    self.logger.warning(f"Telegram character limit ({telegram_char_limit}) exceeded: {current_length}. Stopping updates.")
                
                # Skip updates if "message not modified" error occurred or Telegram limit exceeded
                if message_not_modified_error or telegram_limit_exceeded:
                    if telegram_limit_exceeded and chunk_counter % 10 == 0:
                        self.logger.debug(f"Still collecting content (length: {current_length}), but updates paused due to Telegram limit")
                    continue
                    
                current_time = asyncio.get_event_loop().time()
                time_since_last_update = current_time - last_update_time
                
                # Update message at minimum update interval if not too long
                if time_since_last_update >= min_update_interval and not response_too_long and not telegram_limit_exceeded:
                    try:
                        display_text = full_response + "\n\nTyping..."
                        
                        if len(display_text) > self.max_length:
                            display_text = display_text[:self.max_length - 30] + "...\n\n[Message continues]"
                        
                        self.logger.debug(f"Attempting to update message with {len(display_text)} characters")
                        
                        # Only update when content has changed
                        if display_text != last_successful_update:
                            await message_edit_func(message, display_text)
                            last_successful_update = display_text
                            last_update_time = current_time
                            consecutive_errors = 0
                            self.logger.debug("Message updated successfully")
                        
                    except Exception as e:
                        consecutive_errors += 1
                        error_str = str(e)
                        
                        if "Content of the message was not modified" in error_str:
                            self.logger.info("Message not modified error detected. Stopping intermediate updates.")
                            message_not_modified_error = True
                            continue
                        else:
                            self.logger.error(f"Error updating message with stream chunk: {str(e)}")
                            
                            # Stop intermediate updates if too many consecutive errors
                            if consecutive_errors >= max_consecutive_errors:
                                self.logger.error(f"Too many consecutive errors ({consecutive_errors}). Stopping intermediate updates.")
                                break
            
            # Process final response
            if all_chunks and not error_occurred:
                final_response = all_chunks[-1]
                final_length = len(final_response)
                self.logger.info(f"Stream completed. Final response length: {final_length} characters")
                
                # For Telegram, if the message exceeded the character limit, send as file instead
                if telegram_limit_exceeded:
                    self.logger.info(f"Final response exceeded Telegram limit of {telegram_char_limit} characters - sending as file")
                    try:
                        # Create a temporary file in memory
                        file_obj = io.BytesIO(final_response.encode('utf-8'))
                        file_obj.name = "output.txt"
                        
                        self.logger.debug(f"Created file object with {final_length} bytes")
                        
                        # Send the file
                        self.logger.debug("Attempting to send file...")
                        await send_file_func(message, file_obj)
                        self.logger.info("File sent successfully")
                        
                        # Also update the original message to indicate file was sent
                        try:
                            await message_edit_func(message, "Response too long to display in chat. See the attached file for the full response.")
                        except Exception as edit_error:
                            self.logger.warning(f"Error updating message after sending file: {edit_error}")
                            
                    except Exception as e:
                        self.logger.error(f"Error sending file: {e}")
                        try:
                            # Fallback to truncated message
                            self.logger.debug("Attempting fallback to truncated message...")
                            await message_edit_func(message, f"Message too long ({final_length} chars). File attachment failed: {str(e)}")
                            self.logger.debug("Fallback message sent")
                        except Exception as edit_error:
                            self.logger.error(f"Error sending fallback truncated message: {edit_error}")
                
                # Handle standard long message cases
                elif (final_length > self.max_length or response_too_long) and split_long_messages:
                    self.logger.info(f"Final response length: {final_length} characters - splitting into multiple messages")
                    
                    try:
                        # Split the message into parts
                        message_parts = self._split_message(final_response)
                        self.logger.debug(f"Message split into {len(message_parts)} parts")
                        
                        # Send the first part as an edit to the original message
                        self.logger.debug(f"Sending part 1 ({len(message_parts[0])} chars)")
                        await message_edit_func(message, message_parts[0])
                        
                        # Send the remaining parts as new messages
                        for i in range(1, len(message_parts)):
                            self.logger.debug(f"Sending part {i+1} ({len(message_parts[i])} chars)")
                            await message_edit_func(None, message_parts[i])
                            await asyncio.sleep(0.5)  # Small delay between messages
                            
                    except Exception as e:
                        self.logger.error(f"Error sending split messages: {e}")
                        try:
                            # Fallback to file if splitting fails
                            self.logger.debug("Split message sending failed, attempting file fallback...")
                            file_obj = io.BytesIO(final_response.encode('utf-8'))
                            file_obj.name = "output.txt"
                            await send_file_func(message, file_obj)
                            self.logger.debug("File fallback successful")
                        except Exception as file_error:
                            self.logger.error(f"Error sending file fallback: {file_error}")
                            
                elif (final_length > self.max_length or response_too_long) and not split_long_messages:
                    self.logger.info(f"Final response length: {final_length} characters - sending as file")
                    
                    try:
                        # Create a temporary file in memory
                        file_obj = io.BytesIO(final_response.encode('utf-8'))
                        file_obj.name = "output.txt"
                        
                        # Send the file
                        self.logger.debug("Sending response as file...")
                        await send_file_func(message, file_obj)
                        self.logger.debug("File sent successfully")
                    except Exception as e:
                        self.logger.error(f"Error sending file: {e}")
                        try:
                            # Fallback to truncated message
                            self.logger.debug("Attempting to send truncated message as fallback...")
                            await message_edit_func(message, final_response[:self.max_length] + "...\n\n[Message truncated]")
                            self.logger.debug("Truncated message sent")
                        except Exception as edit_error:
                            self.logger.error(f"Error editing truncated message: {edit_error}")
                else:
                    try:
                        self.logger.debug(f"Sending complete response ({final_length} chars)")
                        await message_edit_func(message, final_response)
                        self.logger.debug("Final response sent successfully")
                    except Exception as e:
                        self.logger.error(f"Error sending final response: {e}")
            elif not error_occurred:
                try:
                    self.logger.warning("No response chunks received")
                    await message_edit_func(message, "Sorry, the API didn't return any response. Please try again later.")
                except Exception as e:
                    self.logger.error(f"Error sending no response message: {e}")
                
        except Exception as e:
            self.logger.error(f"Error in process_stream_with_updates: {str(e)}")
            try:
                await message_edit_func(message, f"Error processing stream: {str(e)}")
            except Exception as send_error:
                self.logger.error(f"Error sending error message: {send_error}")
    
    async def process_stream_without_updates(self, stream_generator, split_long_messages=True):
        """
        Process stream response without updating the message, returns the complete response
        
        Args:
            stream_generator: Stream response generator
            split_long_messages (bool): Whether to split long messages instead of returning a file
            
        Returns:
            str, list, or BytesIO: Complete response text, list of parts, or file object
        """
        full_response = ""
        try:
            async for chunk in self._async_generator_from_sync(stream_generator):
                if chunk.startswith("Error") or chunk.startswith("API returned error"):
                    return f"Sorry, there was an issue with the API: {chunk}"
                    
                full_response = chunk
                
            if full_response:
                if len(full_response) > self.max_length and split_long_messages:
                    # Split the message into parts
                    return self._split_message(full_response)
                elif len(full_response) > self.max_length:
                    # Create temporary file in memory
                    file_obj = io.BytesIO(full_response.encode('utf-8'))
                    file_obj.name = "output.txt"
                    return file_obj
                return full_response
            else:
                return "Sorry, the API didn't return any response. Please try again later."
        except Exception as e:
            return f"Error processing stream: {str(e)}"
    
    def _split_message(self, message):
        """
        Split a long message into multiple parts
        
        Args:
            message (str): The message to split
            
        Returns:
            list: List of message parts
        """
        parts = []
        part_prefix = ""
        
        # If max_length is very small, ensure we have at least some content
        effective_max = max(self.max_length, 100)
        
        # Determine the optimal splitting point slightly below the max length
        # to account for part indicators
        max_part_length = effective_max - 20
        
        while message:
            # Look for natural break points (paragraphs, sentences)
            break_pos = -1
            
            if len(message) <= max_part_length:
                # Last part fits entirely
                parts.append(part_prefix + message)
                break
                
            # Try to find paragraph break
            para_pos = message.rfind("\n\n", 0, max_part_length)
            if para_pos > max_part_length // 2:
                break_pos = para_pos
            else:
                # Try to find line break
                line_pos = message.rfind("\n", 0, max_part_length)
                if line_pos > max_part_length // 2:
                    break_pos = line_pos
                else:
                    # Try to find sentence end
                    for sep in [". ", "! ", "? ", ".\n", "!\n", "?\n"]:
                        sentence_pos = message.rfind(sep, 0, max_part_length - 1)
                        if sentence_pos > max_part_length // 2:
                            break_pos = sentence_pos + 1  # Include the separator
                            break
                            
            # If no good break point, just cut at the max length
            if break_pos <= 0:
                break_pos = max_part_length
                
            part = message[:break_pos]
            message = message[break_pos:]
            
            # Add part indicator for all but possibly the first part
            if parts:
                part_indicator = f"[Part {len(parts) + 1}] "
                parts.append(part_indicator + part)
            else:
                parts.append(part)
                # Set prefix for subsequent parts
                part_prefix = "[Continued] "
        
        # Add part count to first part if multiple parts
        if len(parts) > 1:
            parts[0] = f"[Part 1/{len(parts)}] {parts[0]}"
            
        return parts
    
    async def _async_generator_from_sync(self, sync_gen):
        """
        Convert a synchronous generator to an asynchronous generator
        
        Args:
            sync_gen: Synchronous generator
            
        Yields:
            Items produced by the generator
        """
        loop = asyncio.get_running_loop()
        for item in sync_gen:
            yield item
            await asyncio.sleep(0.01)