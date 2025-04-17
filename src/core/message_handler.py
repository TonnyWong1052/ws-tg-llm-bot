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
    
    async def process_stream_with_updates(self, message, stream_generator, message_edit_func, send_file_func, min_update_interval=3.0):
        """
        Process stream responses and update the message periodically
        
        Args:
            message: Message object
            stream_generator: Stream response generator
            message_edit_func: Function to edit the message
            send_file_func: Function to send a file
            min_update_interval (float): Minimum update interval (seconds)
        """
        full_response = ""
        last_update_time = 0
        consecutive_errors = 0
        max_consecutive_errors = 3
        
        try:
            all_chunks = []
            error_occurred = False
            response_too_long = False
            message_not_modified_error = False
            last_successful_update = ""
            
            # Process streaming content
            async for chunk in self._async_generator_from_sync(stream_generator):
                if isinstance(chunk, str) and (chunk.startswith("Error") or chunk.startswith("API returned error")):
                    error_message = f"Sorry, there was an issue with the API: {chunk}"
                    await message_edit_func(message, error_message)
                    error_occurred = True
                    break
                
                all_chunks.append(chunk)
                full_response = chunk
                
                # Check if response is too long
                if len(full_response) > self.max_length:
                    response_too_long = True
                
                # Skip updates if "message not modified" error occurred
                if message_not_modified_error:
                    continue
                    
                current_time = asyncio.get_event_loop().time()
                time_since_last_update = current_time - last_update_time
                
                # Update message at minimum update interval
                if time_since_last_update >= min_update_interval and not response_too_long:
                    try:
                        display_text = full_response + "\n\nTyping..."
                        
                        if len(display_text) > self.max_length:
                            display_text = display_text[:self.max_length - 30] + "...\n\n[Message continues]"
                        
                        # Only update when content has changed
                        if display_text != last_successful_update:
                            await message_edit_func(message, display_text)
                            last_successful_update = display_text
                            last_update_time = current_time
                            consecutive_errors = 0
                        
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
                
                if len(final_response) > self.max_length or response_too_long:
                    self.logger.info(f"Final response length: {len(final_response)} characters - sending as file")
                    
                    try:
                        # Create a temporary file in memory
                        file_obj = io.BytesIO(final_response.encode('utf-8'))
                        file_obj.name = "output.txt"
                        
                        # Send the file
                        await send_file_func(message, file_obj)
                    except Exception as e:
                        self.logger.error(f"Error sending file: {e}")
                        try:
                            # Fallback to truncated message
                            await message_edit_func(message, final_response[:self.max_length] + "...\n\n[Message truncated]")
                        except Exception as edit_error:
                            self.logger.error(f"Error editing truncated message: {edit_error}")
                else:
                    try:
                        await message_edit_func(message, final_response)
                    except Exception as e:
                        self.logger.error(f"Error sending final response: {e}")
            elif not error_occurred:
                try:
                    await message_edit_func(message, "Sorry, the API didn't return any response. Please try again later.")
                except Exception as e:
                    self.logger.error(f"Error sending no response message: {e}")
                
        except Exception as e:
            self.logger.error(f"Error in process_stream_with_updates: {str(e)}")
            try:
                await message_edit_func(message, f"Error processing stream: {str(e)}")
            except Exception as send_error:
                self.logger.error(f"Error sending error message: {send_error}")
    
    async def process_stream_without_updates(self, stream_generator):
        """
        Process stream response without updating the message, returns the complete response
        
        Args:
            stream_generator: Stream response generator
            
        Returns:
            str or BytesIO: Complete response text or file object
        """
        full_response = ""
        try:
            async for chunk in self._async_generator_from_sync(stream_generator):
                if chunk.startswith("Error") or chunk.startswith("API returned error"):
                    return f"Sorry, there was an issue with the API: {chunk}"
                    
                full_response = chunk
                
            if full_response:
                if len(full_response) > self.max_length:
                    # Create temporary file in memory
                    file_obj = io.BytesIO(full_response.encode('utf-8'))
                    file_obj.name = "output.txt"
                    
                    return file_obj
                return full_response
            else:
                return "Sorry, the API didn't return any response. Please try again later."
        except Exception as e:
            return f"Error processing stream: {str(e)}"
    
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