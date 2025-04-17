from telethon import TelegramClient, events
import asyncio
import os
import time
import sys
import io
import platform

# Add the parent directory to the Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from api.llm_api import LLMClient
from telethon.errors.rpcerrorlist import FloodWaitError
from utils.animations import animated_thinking, INITIAL_MESSAGE_ART, SIMPLE_INITIAL_MESSAGE
from services.unwire_fetch import fetch_unwire_news, fetch_unwire_article, fetch_unwire_recent
import time
# Load environment variables from config/.env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'config', '.env'))

# Create a global variable to track whether llm_client is initialized
_llm_client_initialized = False

API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
PHONE_NUMBER = os.getenv('PHONE_NUMBER')
ENVIRONMENT = os.getenv('ENVIRONMENT', 'test')

client = TelegramClient('session_name', API_ID, API_HASH)
llm_client = LLMClient()

# Ensure LLM client initialization
def ensure_llm_client_initialized():
    global llm_client, _llm_client_initialized
    if not _llm_client_initialized:
        print("Initializing LLM client...")
        # Ensure API keys are set and available
        
        # Reinitialize LLM client
        from api.llm_api import LLMClient
        
        # LLMClient will automatically read API keys from environment variables during initialization
        llm_client = LLMClient()
        
        # Check if API keys exist
        if llm_client.deepseek_api_key:
            print("DeepSeek API key loaded")
        
        if llm_client.github_api_key:
            print("GitHub API key loaded")
        
        if llm_client.grok_api_key:
            print("Grok API key loaded")
        
        if llm_client.openai_api_key:
            print("OpenAI API key loaded")
        
        _llm_client_initialized = True
        print("LLM client initialization completed")

# Ensure llm_client is initialized when the file is loaded
ensure_llm_client_initialized()

class FloodWaitHandler:
    def __init__(self):
        self.last_edit_time = {}
        self.min_edit_interval = 1.5
    
    async def safe_edit_message(self, message, text):
        message_id = f"{message.chat_id}:{message.id}"
        current_time = time.time()
        
        if message_id in self.last_edit_time:
            elapsed = current_time - self.last_edit_time[message_id]
            if elapsed < self.min_edit_interval:
                await asyncio.sleep(self.min_edit_interval - elapsed)
        
        try:
            await message.edit(text)
            self.last_edit_time[message_id] = time.time()
            return True
        
        except FloodWaitError as e:
            wait_seconds = getattr(e, 'seconds', 60)
            
            if wait_seconds <= 15:
                print(f"FloodWaitError: Waiting for {wait_seconds} seconds before retrying")
                await asyncio.sleep(wait_seconds)
                try:
                    await message.edit(text)
                    self.last_edit_time[message_id] = time.time()
                    return True
                except Exception as e2:
                    print(f"Failed to edit message after waiting: {str(e2)}")
            else:
                print(f"FloodWaitError with long wait time ({wait_seconds} seconds). Skipping edit.")
            
            return False
            
        except Exception as e:
            print(f"Error editing message: {str(e)}")
            return False

flood_handler = FloodWaitHandler()

async def create_llm_task(provider, prompt, **kwargs):
    return asyncio.create_task(
        asyncio.to_thread(llm_client.call_llm, provider, prompt, **kwargs)
    )

async def handle_llm_request(event, llm_type, prompt, model_name=None, system_prompt=None, display_name=None):
    """
    Handles LLM requests for various models (grok, deepseek, etc.)
    """
    # Initialize variables to keep track of messages
    original_message = event.message
    response_message = None
    
    try:
        # Send initial response message
        response_message = await event.respond("處理中，請稍等...")
        
        # Initialize LLMClient if not already done
        global llm_client, _llm_client_initialized
        if not _llm_client_initialized:
            ensure_llm_client_initialized()
        
        model = model_name if model_name else llm_type

        # Get appropriate stream generator based on LLM type
        if llm_type == 'deepseek':
            # For DeepSeek, use call_deepseek_stream with the proper parameters
            stream_generator = llm_client.call_deepseek_stream(prompt, model=model, mode="reasoner")
        elif llm_type == 'grok':
            # For Grok, use call_grok3_stream with the proper parameters
            stream_generator = llm_client.call_grok3_stream(system_prompt, prompt, model_name=model)
        else:
            await response_message.edit("不支持的 LLM 類型")
            return
        
        # Process the stream and update the message
        await process_stream_with_updates(message_obj=response_message, stream_generator=stream_generator)
    
    except FloodWaitError as e:
        wait_seconds = e.seconds
        print(f"FloodWaitError in handle_llm_request: {wait_seconds}s wait required")
        
        try:
            if response_message:
                await response_message.edit(f"Telegram 速率限制已觸發，需要等待 {wait_seconds} 秒。請稍後再試。")
            else:
                await event.respond(f"Telegram 速率限制已觸發，需要等待 {wait_seconds} 秒。請稍後再試。")
        except Exception as edit_error:
            print(f"Unable to edit/send rate limit message: {edit_error}")
    
    except Exception as e:
        print(f"Error in handle_llm_request: {e}")
        import traceback
        traceback.print_exc()
        
        # Try to send error message
        try:
            if response_message:
                await response_message.edit(f"出錯了: {str(e)}")
            else:
                await event.reply(f"出錯了: {str(e)}")
        except Exception as reply_error:
            print(f"Unable to send error message: {reply_error}")

async def safe_send_message(message_obj, text, event=None, parse_mode=None):
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
            print(f"FloodWaitError in safe_send_message (file path): {wait_seconds}s wait required")
            
            # If wait time isn't too long, wait and retry
            if wait_seconds <= 180:  # Maximum wait of 3 minutes
                try:
                    print(f"Waiting {wait_seconds} seconds before retry...")
                    await asyncio.sleep(wait_seconds + 1)  # Wait an extra second to ensure safety
                    await message_obj.edit(file=text)
                    return True
                except Exception as retry_e:
                    print(f"Retry failed after waiting: {retry_e}")
            
            # Try to read file content and send memory file
            try:
                with open(text, "rb") as f:
                    file_content = f.read()
                file_obj = io.BytesIO(file_content)
                file_obj.name = os.path.basename(text)
                
                # Wait again before trying to edit to avoid triggering rate limits
                await asyncio.sleep(2)
                await message_obj.edit(file=file_obj)
                return True
            except FloodWaitError as e2:
                print(f"Second FloodWaitError: {e2.seconds}s wait required. Giving up.")
                return False
            except Exception as e2:
                print(f"Error sending file from memory after reading {text}: {e2}")
                # Continue with normal processing, try to send text
    
    # Handle normal text
    if len(text) > TELEGRAM_MAX_LENGTH:
        try:
            # Create a temporary file in memory instead of saving to disk
            import io
            file_obj = io.BytesIO(text.encode('utf-8'))
            file_obj.name = "output.txt"
            
            # Edit the message to send the file
            await message_obj.edit(file=file_obj)
            return True
        except FloodWaitError as e:
            wait_seconds = e.seconds
            print(f"FloodWaitError in safe_send_message (memory file): {wait_seconds}s wait required")
            
            # If wait time isn't too long, wait and retry
            if wait_seconds <= 180:  # Maximum wait of 3 minutes
                try:
                    print(f"Waiting {wait_seconds} seconds before retry...")
                    await asyncio.sleep(wait_seconds + 1)
                    await message_obj.edit(file=file_obj)
                    return True
                except Exception as retry_e:
                    print(f"Failed to edit message after waiting: {retry_e}")
            
            # If still failing, try to save to disk and send the file
            try:
                if not os.path.exists('logs'):
                    os.makedirs('logs')
                
                file_path = "logs/output.txt"
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(text)
                
                # Wait again before trying to edit to avoid triggering rate limits
                await asyncio.sleep(2)
                await message_obj.edit(file=file_path)
                return True
            except Exception as file_e:
                print(f"Error sending disk file: {file_e}")
            
            # If all attempts fail, only send truncated message as a last resort
            if event is not None:
                for retry in range(max_retry_times):
                    try:
                        truncated_msg = text[:TELEGRAM_MAX_LENGTH - 100] + "...\n\n[Message too long, truncated]"
                        await event.respond(truncated_msg)
                        return True
                    except FloodWaitError as respond_e:
                        # If this is the last retry, give up
                        if retry == max_retry_times - 1:
                            print(f"Final FloodWaitError: {respond_e.seconds}s required. Giving up.")
                            return False
                        
                        # Otherwise wait and retry
                        wait_time = respond_e.seconds
                        print(f"FloodWaitError in respond: {wait_time}s required. Waiting...")
                        await asyncio.sleep(wait_time + 1)
                    except Exception as respond_error:
                        print(f"Error sending reply message: {respond_error}")
                        break
            
            return False
        except Exception as e:
            print(f"Error sending file: {e}")
            # Try to send a new message as a last resort
            if event is not None:
                for retry in range(max_retry_times):
                    try:
                        truncated_msg = text[:TELEGRAM_MAX_LENGTH - 100] + "...\n\n[Message too long, truncated]"
                        await event.respond(truncated_msg)
                        return True
                    except FloodWaitError as respond_e:
                        # If this is the last retry, give up
                        if retry == max_retry_times - 1:
                            print(f"Final FloodWaitError: {respond_e.seconds}s required. Giving up.")
                            return False
                        
                        # Otherwise wait and retry
                        wait_time = respond_e.seconds
                        print(f"FloodWaitError in respond: {wait_time}s required. Waiting...")
                        await asyncio.sleep(wait_time + 1)
                    except Exception as respond_error:
                        print(f"Error sending reply message: {respond_error}")
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
                print(f"FloodWaitError in safe_send_message: {wait_seconds}s wait required (retry {retry_count+1}/{max_retry_times+1})")
                
                # Last retry, if wait time is too long, give up
                if retry_count == max_retry_times or wait_seconds > 180:
                    break
                
                # Otherwise wait and retry
                try:
                    print(f"Waiting {wait_seconds} seconds before retry...")
                    await asyncio.sleep(wait_seconds + 1)
                    retry_count += 1
                except Exception as sleep_error:
                    print(f"Error during sleep: {sleep_error}")
                    break
                
            except Exception as e:
                error_str = str(e)
                if "Content of the message was not modified" in error_str:
                    print("Message not modified error in safe_send_message. This is usually harmless.")
                    return True  # Consider as success since content didn't change
                    
                print(f"Error in safe_send_message: {e}")
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
                        print(f"Final FloodWaitError: {respond_e.seconds}s required. Giving up.")
                        return False
                    
                    # Otherwise wait and retry
                    wait_time = respond_e.seconds
                    print(f"FloodWaitError in respond: {wait_time}s required. Waiting...")
                    await asyncio.sleep(wait_time + 1)
                except Exception as reply_e:
                    print(f"Failed to send new message: {reply_e}")
                    if retry == max_retry_times - 1:
                        return False
                    # Continue to next retry
                    await asyncio.sleep(2)
        
        # If all attempts fail, return failure
        return False

# Add basic command handlers
@client.on(events.NewMessage(pattern=r'^/ping$'))
async def ping_handler(event):
    try:
        # Get current timestamp
        start_time = time.time()
        
        # Reply with initial message
        message = await event.reply("Pinging...")
        
        # Calculate latency
        latency = round((time.time() - start_time) * 1000, 2)
        
        # Determine service type and location
        service_type = "Local"
        location = "Unknown"
        
        # Check if running in Azure (you can add more detailed checks)
        if os.getenv('AZURE_DEPLOYMENT') or os.getenv('AZURE_WEBSITE_NAME'):
            service_type = "Azure"
        
        # Create compact response format
        response = f"{latency}ms\nService: {service_type}\nLocation: {location}"
        
        # Update message with response
        await message.edit(response)
    except FloodWaitError as e:
        wait_seconds = e.seconds
        print(f"FloodWaitError in ping_handler: {wait_seconds}s wait required")
        
        try:
            await event.respond(f"Telegram rate limit triggered, need to wait {wait_seconds} seconds. Please try again later.")
        except Exception as respond_error:
            print(f"Unable to send rate limit notification: {respond_error}")
    except Exception as e:
        print(f"Error in ping handler: {e}")
        try:
            await event.reply(f"Error: {str(e)}")
        except Exception as reply_error:
            print(f"Unable to send error message: {reply_error}")

@client.on(events.NewMessage(pattern=r'^/env$'))
async def env_handler(event):
    try:
        # Get environment information
        environment = os.getenv('ENVIRONMENT', 'Not set')
              
        # Format response
        response = f"Environment: {environment.upper()}\n\n"
        
        # System information
        system_info = f"OS: {os.name} {platform.system()} {platform.release()}"
        python_info = f"Python: {platform.python_version()}"
        
        # Bot status
        bot_info = "Bot is running"
        llm_status = "LLM Client: Connected" if _llm_client_initialized else "LLM Client: Not initialized"
        
        # Add system info to response
        response += f"{system_info}\n{python_info}\n\n{bot_info}\n{llm_status}"
        
        await event.reply(response)
    except FloodWaitError as e:
        wait_seconds = e.seconds
        print(f"FloodWaitError in env_handler: {wait_seconds}s wait required")
        
        try:
            await event.respond(f"Telegram rate limit triggered, need to wait {wait_seconds} seconds. Please try again later.")
        except Exception as respond_error:
            print(f"Unable to send rate limit notification: {respond_error}")
    except Exception as e:
        print(f"Error in env handler: {e}")
        try:
            await event.reply(f"Error: {str(e)}")
        except Exception as reply_error:
            print(f"Unable to send error message: {reply_error}")

@client.on(events.NewMessage(pattern=r'^/hi_dog$'))
async def hi_dog_handler(event):
    try:
        # Dog ASCII arts
        dog_arts = [
            """
⠀⠀⠀⠀⠀⠀⢀⣀⣀⣀⣀⣀⣀⣀⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⢀⡤⠞⠋⠉⠀⠀⠀⠀⠀⠀⠀⠉⠙⠳⢄⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⣠⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠱⡆⠀⠀⠀⠀⠀⠀⠀⠀
⢠⠇⠀⢰⠆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠰⡄⠀⢸⡀⠀⠀⠀⠀⠀⠀⠀    Sit, Stay,'N Play
⢸⠀⠀⢸⠀⠀⢰⣶⡀⠀⠀⠀⢠⣶⡀⠀⠀⡇⠀⢸⠂⠀⠀⠀⠀⠀⠀⠀
⠈⢧⣀⢸⡄⠀⠀⠉⠀⠀⠀⠀⠀⠉⠀⠀⢠⡇⣠⡞⠁⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠉⠙⣇⠀⠂⠀⠀⢶⣶⣶⠀⠄⠀⠀⣾⠉⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠘⢦⡀⠀⠀⠀⠀⠀⠀⠀⢀⣼⡁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⢠⠞⠓⠤⣤⣀⣀⣠⣤⠴⠚⠉⠑⠲⢤⡀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⢸⠀⠀⣀⣠⣀⣀⣠⣀⡀⠀⠀⠀⠀⠀⠈⠳⣄⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⢸⠀⠰⡇⠀⠈⠁⠀⠈⡧⠀⠀⠀⠀⠀⠀⠀⠈⢦⠀⠀⢠⠖⡆
⠀⠀⠀⠀⢸⠀⠀⠑⢦⡀⠀⣠⠞⠁⠀⢸⠀⠀⠀⠀⠀⠀⠈⣷⠞⠋⢠⠇
⠀⠀⠀⠀⢸⠀⠀⠀⠀⠙⡞⠁⠀⠀⠀⢸⠀⠀⠀⠀⠀⠀⠀⢹⢀⡴⠋⠀
⠀⠀⠀⠀⢸⠀⠀⠀⠀⠀⡇⠀⠀⠀⠀⢸⠀⠀⠀⠀⠀⠀⠀⡞⠉⠀⠀⠀
⠀⠀⠀⠀⢸⡀⠀⠀⠀⢠⣧⠀⠀⠀⠀⣸⡀⠀⠀⠀⠀⣠⠞⠁⠀⠀⠀⠀
⠀⠀⠀⠀⠈⠳⠦⠤⠴⠛⠈⠓⠤⠤⠞⠁⠉⠛⠒⠚⠋⠁⠀⠀⠀⠀⠀⠀
            """,
            """
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣀⣠⣤⣄⣀⣀⣀⡀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⠶⠋⠉⠙⢿⣿⣿⣿⣄⠈⢻⣶⠤⣄⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣾⠏⠀⠀⠀⠀⠈⣿⠋⠉⠙⢧⡀⢿⡄⢸⣷⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⢀⣀⣾⣿⣷⣄⠀⠀⠀⠀⠀⠀⣴⣶⣶⡄⢸⡇⢸⡟⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⡏⣉⢻⣿⠟⠋⠀⠀⠀⠀⠀⠀⠿⠒⠻⣧⢸⡇⣿⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⡇⢻⡀⠻⡄⠀⣶⣿⣷⠀⠀⠀⣀⡀⠀⠈⠻⣧⢻⣄⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⣷⠸⣷⣄⣹⣆⣿⠋⠁⠀⠠⣿⣿⣟⠀⠀⢀⡿⠿⠿⠃⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⢿⣄⠀⠈⠉⠛⢷⢰⠆⠀⠀⠀⠛⣿⠗⣺⣿⠁⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠙⠛⢻⣶⣄⣸⠦⠤⠤⠤⠾⠥⠚⠹⣿⣇⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⡴⠻⣿⠋⠛⠀⠀⠀⠀⠀⠀⠀⠀⢈⣿⡄⠀⠀⠀⠀
⠀⣠⢖⣢⠀⢀⠀⠀⢀⣴⣿⠁⠀⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠻⣧⠀⠀⠀⠀
⣾⣿⠋⣠⣾⠛⠀⣴⡿⠛⣿⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⠀⠀⠀⠀
⠈⠁⣰⡿⠁⢀⣾⠟⠁⠀⢻⣷⡄⠀⠀⠀⠀⠀⣀⠀⠀⠀⠀⠀⠀⡘⢿⡆⠀⠀⠀
⠀⠀⣿⡇⠀⣼⠃⠀⠀⠀⠈⣿⣿⡄⠀⠀⠀⠘⣿⠇⠀⠀⠀⠀⣠⣧⠈⢷⠀⠀⠀
⠀⠀⣿⣇⢰⣿⠀⠀⠀⠀⠀⣿⣿⣿⡄⠀⠀⠀⡟⠀⠀⠀⣠⣴⣿⠃⠀⠘⡆⠀⠀
⠀⠀⢹⣿⣾⣧⠀⠀⠀⠀⣸⣿⣿⣿⡇⠀⠀⠀⢹⣦⣴⣾⣿⢿⡿⠀⠀⠀⣧⠀⠀
⠀⠀⠈⢻⣿⣿⣄⣼⣿⣶⣿⣿⣿⣿⣷⠀⠀⢀⣸⣿⡿⠟⠁⢸⠇⠀⢤⡾⠿⣦⡀
⠀⠀⠀⠀⠙⢿⡟⠉⠉⠉⠁⠈⠻⡏⠀⠰⠶⠛⠋⢹⡄⠀⠀⠸⡄⢀⠀⢸⡔⣆⢳
⠀⠀⠀⠀⠀⠀⠹⠤⠼⠤⠼⠷⠞⢷⣀⡀⠀⢰⠀⣦⣷⠀⠀⠀⠉⠙⠒⠚⠳⠞⠋
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⠛⠉⠛⠉⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀""",
"""
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⡀⠀⠀⠀⠀
⠀⠀⠀⠀⢀⡴⣆⠀⠀⠀⠀⠀⣠⡀ ᶻ 𝗓 𐰁 .ᐟ ⣼⣿⡗⠀⠀⠀⠀
⠀⠀⠀⣠⠟⠀⠘⠷⠶⠶⠶⠾⠉⢳⡄⠀⠀⠀⠀⠀⣧⣿⠀⠀⠀⠀⠀
⠀⠀⣰⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢻⣤⣤⣤⣤⣤⣿⢿⣄⠀⠀⠀⠀
⠀⠀⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣧⠀⠀⠀⠀⠀⠀⠙⣷⡴⠶⣦
⠀⠀⢱⡀⠀⠉⠉⠀⠀⠀⠀⠛⠃⠀⢠⡟⠀⠀⠀⢀⣀⣠⣤⠿⠞⠛⠋
⣠⠾⠋⠙⣶⣤⣤⣤⣤⣤⣀⣠⣤⣾⣿⠴⠶⠚⠋⠉⠁⠀⠀⠀⠀⠀⠀
⠛⠒⠛⠉⠉⠀⠀⠀⣴⠟⢃⡴⠛⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
""",
"""⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⢠⣿⣿⣦⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣴⣿⣦⡀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⢠⣿⣿⣿⣿⣆⠀⠀⠀⠀⠀⠀⠀⠀⣾⣿⣿⣿⣷⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⢀⣾⣿⣿⣿⣿⣿⡆⠀⠀⠀⠀⠀⠀⣸⣿⣿⣿⣿⣿⡆⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⣾⣿⣿⣿⣿⣿⣿⣿⡀⠀⠀⠀⠀⢀⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣧⠀⠀⠀⠀⣼⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀
⠀⠀⠀⠀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣠⣤⣤⣼⣿⣿⣿⣿⣿⣿⣿⣿⣷⠀⠀⠀⠀⠀
⠀⠀⠀⢀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀
⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀
⠀⠀⠀⠘⣿⣿⣿⣿⠟⠁⠀⠀⠀⠹⣿⣿⣿⣿⣿⠟⠁⠀⠀⠹⣿⣿⡿⠀⠀⠀⠀⠀
⠀⠀⠀⠀⣿⣿⣿⡇⠀⠀⠀⢼⣿⠀⢿⣿⣿⣿⣿⠀⣾⣷⠀⠀⢿⣿⣷⠀⠀⠀⠀⠀
⠀⠀⠀⢠⣿⣿⣿⣷⡀⠀⠀⠈⠋⢀⣿⣿⣿⣿⣿⡀⠙⠋⠀⢀⣾⣿⣿⠀⠀⠀⠀⠀
⢀⣀⣀⣀⣿⣿⣿⣿⣿⣶⣶⣶⣶⣿⣿⣿⣿⣾⣿⣷⣦⣤⣴⣿⣿⣿⣿⣤⠤⢤⣤⡄
⠈⠉⠉⢉⣙⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣇⣀⣀⣀⡀⠀
⠐⠚⠋⠉⢀⣬⡿⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⣥⣀⡀⠈⠀⠈⠛
⠀⠀⠴⠚⠉⠀⠀⠀⠉⠛⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠛⠋⠁⠀⠀⠀⠉⠛⠢⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⣸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⣰⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⢠⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⢠⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⢠⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⢠⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡄⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀""",
"""
                             ＿＿
　　　　　🌸＞　　フ
　　　　　| 　_　 _ l
　 　　　／` ミ＿xノ
　　 　 /　　　 　 |
　　　 /　 ヽ　　 ﾉ
　 　 │　　|　|　|
　／￣|　　 |　|　|
　| (￣ヽ＿_ヽ_)__)
　＼二つ"""
        ]
        
        # Choose a random dog art
        import random
        dog_art = random.choice(dog_arts)
        
        await event.reply(f"Woof! Hello there! 🐶\n{dog_art}")
    except FloodWaitError as e:
        wait_seconds = e.seconds
        print(f"FloodWaitError in hi_dog_handler: {wait_seconds}s wait required")
        
        try:
            await event.respond(f"Telegram rate limit triggered, need to wait {wait_seconds} seconds. Please try again later.")
        except Exception as respond_error:
            print(f"Unable to send rate limit notification: {respond_error}")
    except Exception as e:
        print(f"Error in hi_dog handler: {e}")
        try:
            await event.reply(f"Error: {str(e)}")
        except Exception as reply_error:
            print(f"Unable to send error message: {reply_error}")

@client.on(events.NewMessage(pattern=r'^/test$'))
async def test_handler(event):
    try:
        await event.reply("Bot is working! This is a test response.")
    except Exception as e:
        print(f"Error in test handler: {e}")

@client.on(events.NewMessage(pattern=r'/deepseek\s*(.*)'))
async def deepseek_handler(event):
    """Handler for /deepseek command"""
    # Get the prompt from the message
    prompt = event.pattern_match.group(1).strip()
    
    # If the prompt is empty, return a help message
    if not prompt:
        await event.reply("請提供要處理的內容：/deepseek 你的問題或請求")
        return
    
    # Use the handle_llm_request for processing
    system_prompt = "You are DeepSeek Coder, a helpful coding assistant. Always provide clear and concise responses."
    await handle_llm_request(event, 'deepseek', prompt, model_name="deepseek-coder-33b-instruct", 
                           system_prompt=system_prompt, display_name="DeepSeek Coder")

@client.on(events.NewMessage(pattern=r'/r1\s*(.*)'))
async def r1_handler(event):
    """Handler for /r1 command"""
    # Get the prompt from the message
    prompt = event.pattern_match.group(1).strip()
    
    await event.reply(f"Woof! Hello there! 🐶\n")
    # If the prompt is empty, return a help message
    if not prompt:
        await event.reply("請提供要處理的內容：/r1 你的問題或請求")
        return
    
    # Use the handle_llm_request for processing
    system_prompt = "You are a helpful AI assistant called R1. Always provide detailed and accurate responses."
    await handle_llm_request(event, 'deepseek', prompt, model_name="meta-llama/Meta-Llama-3-70B-Instruct",
                           system_prompt=system_prompt, display_name="R1")

@client.on(events.NewMessage(pattern=r'/gpt\s*(.*)', incoming=True))
async def gpt_handler(event):
    """Handler for /gpt command"""
    # Get the prompt from the message
    prompt = event.pattern_match.group(1).strip()
    
    # If the prompt is empty, return a help message
    if not prompt:
        await event.reply("請提供要處理的內容：/gpt 你的問題或請求")
        return
    
    # Use the handle_llm_request for processing
    system_prompt = "You are a helpful AI assistant called GPT. Always provide clear and comprehensive responses."
    await handle_llm_request(event, 'gpt', prompt, 
                           system_prompt=system_prompt, display_name="GPT")

@client.on(events.NewMessage(pattern=r'/grok\s*(.*)', incoming=True))
async def grok_api_handler(event):
    """Handler for /grok command"""
    # Get the prompt from the message
    prompt = event.pattern_match.group(1).strip()
    
    # If the prompt is empty, return a help message
    if not prompt:
        await event.reply("請提供要處理的內容：/grok 你的問題或請求")
        return
    
    # Use the handle_llm_request for processing
    system_prompt = "You are a helpful AI assistant called Grok. Always provide clear, detailed and accurate responses."
    await handle_llm_request(event, 'grok3', prompt, 
                           system_prompt=system_prompt, display_name="Grok")

@client.on(events.NewMessage(pattern=r'^/grok_think (.+)'))
async def grok_think_api_handler(event):
    try:
        prompt = event.pattern_match.group(1).strip()
        await handle_grok3_stream_request(event, prompt)
    except FloodWaitError as e:
        # Directly handle top-level FloodWaitError
        wait_seconds = e.seconds
        print(f"FloodWaitError in grok_think_api_handler: {wait_seconds}s wait required")
        
        try:
            # Try to send a notification instead of retrying immediately
            await event.respond(f"Telegram rate limit triggered, need to wait {wait_seconds} seconds. Please try again later.")
        except Exception as respond_error:
            print(f"Unable to send rate limit notification: {respond_error}")
    except Exception as e:
        print(f"Unhandled exception in grok_think_api_handler: {e}")
        import traceback
        traceback.print_exc()

async def process_stream_with_updates(message_obj, stream_generator, min_update_interval=1.5):
    """
    Process a streaming response and update the message with chunks
    
    Args:
        message_obj: The Telegram message object to update
        stream_generator: Generator yielding chunks of text
        min_update_interval: Minimum time between updates in seconds
    """
    full_response = ""
    last_update_time = time.time()
    error_message = None
    
    try:
        for chunk in stream_generator:
            if chunk is None:
                continue
                
            # Check if chunk contains an error message
            if isinstance(chunk, str) and (chunk.startswith("Error:") or chunk.startswith("Sorry, an error occurred")):
                error_message = chunk
                break
                
            # Add chunk to full response
            if isinstance(chunk, str):
                full_response += chunk
            
            # Only update if enough time has passed since the last update
            current_time = time.time()
            if current_time - last_update_time >= min_update_interval:
                try:
                    # Check if response is too long for a single message
                    if len(full_response) > 4000:
                        # Create a temporary file in memory
                        file_obj = io.BytesIO(full_response.encode('utf-8'))
                        file_obj.name = "response.txt"
                        
                        # Edit the message to send the file
                        await message_obj.edit(file=file_obj)
                    else:
                        await message_obj.edit(full_response)
                        
                    last_update_time = current_time
                except FloodWaitError as e:
                    print(f"FloodWaitError in stream update: {e.seconds}s wait required")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    if "not modified" not in str(e).lower():
                        print(f"Error updating message in stream: {e}")
    except Exception as e:
        print(f"Error in process_stream_with_updates: {e}")
        error_message = f"Error processing stream: {str(e)}"
    
    # Handle final response
    if error_message:
        try:
            await message_obj.edit(error_message)
        except Exception as e:
            print(f"Error sending error message: {e}")
    elif full_response:
        try:
            # Check if response is too long for a single message
            if len(full_response) > 4000:
                # Create a temporary file in memory
                file_obj = io.BytesIO(full_response.encode('utf-8'))
                file_obj.name = "response.txt"
                
                # Edit the message to send the file
                await message_obj.edit(file=file_obj)
            else:
                await message_obj.edit(full_response)
        except Exception as e:
            print(f"Error sending final response: {e}")
    else:
        try:
            await message_obj.edit("No response received from API.")
        except Exception as e:
            print(f"Error sending no response message: {e}")

async def show_limited_thinking_animation(message, max_updates=5, interval=3):
    """
    Show limited thinking animation on a message
    
    Args:
        message: The message object to animate
        max_updates: Maximum number of animation updates
        interval: Seconds between updates
    """
    thinking_frames = [
        "Thinking.",
        "Thinking..",
        "Thinking...",
        "Thinking....",
    ]
    
    try:
        for i in range(max_updates):
            frame = thinking_frames[i % len(thinking_frames)]
            try:
                await message.edit(frame)
            except FloodWaitError as e:
                print(f"FloodWaitError in thinking animation: {e.seconds}s wait required")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                if "not modified" not in str(e).lower():
                    print(f"Error updating thinking animation: {e}")
            
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        # Animation was cancelled, this is normal
        return
    except Exception as e:
        print(f"Error in thinking animation: {e}")

async def handle_grok3_stream_request(event, prompt):
    try:
        thinking_msg = await event.reply(INITIAL_MESSAGE_ART)
    except FloodWaitError as e:
        print(f"FloodWaitError with art message: {e.seconds} seconds wait required. Using simple message instead.")
        await asyncio.sleep(2)
        thinking_msg = await event.reply(SIMPLE_INITIAL_MESSAGE)
    except Exception as e:
        print(f"Error sending initial message: {e}. Using simple message instead.")
        thinking_msg = await event.reply(SIMPLE_INITIAL_MESSAGE)
    
    error_occurred = False
    max_retries = 3
    retry_delay = 2
    
    try:
        if llm_client.environment.lower() == 'test':
            test_task = asyncio.create_task(asyncio.to_thread(llm_client.call_test, prompt))
            response = await animated_thinking(thinking_msg, test_task)
            await safe_send_message(thinking_msg, response)
            return
            
        # Check if Grok API key is available
        if not llm_client.grok_api_key:
            error_msg = "Grok API key not found. Please set GROK_API_KEY in your environment variables or credentials file."
            await safe_send_message(thinking_msg, error_msg, event=event)
            return
            
        model = "grok-3-reasoner"
        system_prompt = "You are a helpful AI assistant with reasoning capabilities. Think through problems step by step and explore different aspects of the question. Format your response clearly with proper spacing, line breaks, and structure. Use markdown-style formatting like *bold*, _italic_, and `code` for emphasis. Use numbered lists (1., 2., 3.) and bullet points (- or *) for lists. Ensure your response is well-structured and easy to read."
        
        # Start with animation
        animation_task = asyncio.create_task(show_limited_thinking_animation(thinking_msg))
        
        # Ensure LLM client is initialized
        ensure_llm_client_initialized()
        
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
                
                # Set a timeout for the API call
                stream_generator = llm_client.call_grok3_stream(system_prompt, prompt, model_name=model)
                
                # Cancel animation when we get the first response
                animation_task.cancel()
                
                # Process the stream with a timeout
                async with asyncio.timeout(180):  # Increased to 180 seconds timeout
                    await process_stream_with_updates(thinking_msg, stream_generator)
                grok_success = True
                return  # If successful, return directly
                
            except asyncio.TimeoutError:
                error_str = "Request timed out, possibly due to high server load"
                if attempt < max_retries - 1:
                    retry_wait = retry_delay * (2 ** attempt)  # Exponential backoff
                    try:
                        await thinking_msg.edit(f"API request timed out, retrying in {retry_wait} seconds... (attempt {attempt + 1}/{max_retries})")
                    except Exception as edit_error:
                        print(f"Error editing message during retry: {edit_error}")
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
                            print(f"Error editing message during retry: {edit_error}")
                        await asyncio.sleep(retry_wait)
                        continue
                    else:
                        # All retries have failed
                        try:
                            await thinking_msg.edit("Grok API currently unavailable, switching to DeepSeek model...")
                        except Exception as edit_error:
                            print(f"Error editing message after all retries: {edit_error}")
                        break
                elif "Content of the message was not modified" in error_str:
                    # If it's a message not modified error, try using the backup model
                    print("Message not modified error detected. Switching to DeepSeek model...")
                    try:
                        await thinking_msg.edit("Message update error. Switching to DeepSeek model...")
                    except Exception as edit_error:
                        print(f"Error editing message for model switch: {edit_error}")
                    break
                else:
                    error_msg = f"Sorry, an error occurred: {str(e)}"
                    await safe_send_message(thinking_msg, error_msg, event=event)
                    error_occurred = True
                    break
        
        # If Grok API failed, try using backup model
        if not grok_success:
            try:
                # Use DeepSeek as backup model
                model = "deepseek-coder-33b-instruct"
                stream_generator = llm_client.call_deepseek_stream(prompt, model=model, mode="reasoner")
                
                # Show message that we're using the backup model
                try:
                    await thinking_msg.edit("Using DeepSeek model to process request...")
                except:
                    pass
                
                # Process streaming response
                await process_stream_with_updates(thinking_msg, stream_generator)
                return
                
            except Exception as e:
                error_msg = f"Both Grok API and DeepSeek model failed. Error: {str(e)}"
                await safe_send_message(thinking_msg, error_msg, event=event)
                error_occurred = True
                
    except FloodWaitError as e:
        wait_seconds = e.seconds
        print(f"FloodWaitError when updating response: {wait_seconds} seconds wait required")
        
        error_msg = f"Response was generated but Telegram rate limits were hit. Please try again in {wait_seconds} seconds."
        await safe_send_message(thinking_msg, error_msg, event=event)
        error_occurred = True
            
    except Exception as e:
        error_msg = f"Sorry, an error occurred: {str(e)}"
        await safe_send_message(thinking_msg, error_msg, event=event)
        error_occurred = True
            
        print(f"Error in grok3_stream_handler: {str(e)}")
        
    if error_occurred:
        # Provide additional information about the error
        try:
            await asyncio.sleep(1)  # Small delay before sending additional info
            await event.reply("If you continue to experience Grok API issues, please try:\n\n"
                             "1. Using other models (e.g., /deepseek or /gpt)\n"
                             "2. Wait a few minutes and try again\n"
                             "3. Check if Grok API service is available")
        except Exception as e:
            print(f"Error sending additional error information: {str(e)}")

@client.on(events.NewMessage(pattern=r'^/\.env$'))
async def dotenv_handler(event):
    # Call the same handler as /env
    await env_handler(event)

async def main():
    environment = os.getenv('ENVIRONMENT')
    print(f"Starting userbot in {environment.upper() if environment else 'PROD'} mode...")
    
    # Ensure llm_client is initialized
    ensure_llm_client_initialized()
    
    # Check if we're running in a non-interactive environment (like a server)
    is_interactive = os.isatty(sys.stdin.fileno()) if hasattr(sys, 'stdin') and hasattr(sys.stdin, 'fileno') else False
    
    # Check if client is connected
    try:
        if not client.is_connected():
            print("Telegram client not connected, connecting...")
            if not is_interactive:
                print("Running in non-interactive mode, using session-only authentication")
                # In non-interactive mode, only use existing session
                try:
                    # Start without phone to avoid code prompt
                    await client.start()
                    if not await client.is_user_authorized():
                        print("ERROR: Not authorized and cannot request code in non-interactive mode")
                        print("Please run scripts/setup_session.py on a machine with an interactive terminal first")
                        return False
                except Exception as e:
                    print(f"Failed to start client in non-interactive mode: {str(e)}")
                    return False
            else:
                # Interactive mode - normal flow with phone parameter
                try:
                    await client.start(phone=PHONE_NUMBER)
                except Exception as e:
                    print(f"Error starting client: {str(e)}")
                    return False
        else:
            print("Telegram client is connected")
        
        print("Userbot is running...")
        await client.run_until_disconnected()
        return True
    except Exception as e:
        print(f"Error starting Userbot: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

# If this file is run directly, run the main function
# If imported as a module, only define functions without executing
if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Unhandled exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)