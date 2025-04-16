from telethon import TelegramClient, events
import asyncio
import os
import time
import sys
import re

# Add the parent directory to the Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from api.llm_api import LLMClient
from telethon.errors.rpcerrorlist import FloodWaitError
from utils.animations import animated_thinking, INITIAL_MESSAGE_ART, SIMPLE_INITIAL_MESSAGE
from services.unwire_fetch import fetch_unwire_news, fetch_unwire_article, fetch_unwire_recent

# Load environment variables from config/.env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'config', '.env'))

API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
PHONE_NUMBER = os.getenv('PHONE_NUMBER')
ENVIRONMENT = os.getenv('ENVIRONMENT', 'test')

client = TelegramClient('session_name', API_ID, API_HASH)
llm_client = LLMClient()

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

async def handle_llm_request(event, provider, prompt, model_name=None, system_prompt=None, display_name=None):
    display_name = display_name or provider.capitalize()
    
    try:
        thinking_msg = await event.reply(INITIAL_MESSAGE_ART)
    except FloodWaitError as e:
        print(f"FloodWaitError with art message: {e.seconds} seconds wait required. Using simple message instead.")
        await asyncio.sleep(2)
        thinking_msg = await event.reply(SIMPLE_INITIAL_MESSAGE)
    except Exception as e:
        print(f"Error sending initial message: {e}. Using simple message instead.")
        thinking_msg = await event.reply(SIMPLE_INITIAL_MESSAGE)
    
    response = None
    
    try:
        kwargs = {}
        if model_name:
            kwargs['model'] = model_name
        if system_prompt:
            kwargs['system_prompt'] = system_prompt
            
        llm_task = await create_llm_task(provider, prompt, **kwargs)
        
        response = await animated_thinking(thinking_msg, llm_task)
        
        await safe_send_message(thinking_msg, response)
        
    except FloodWaitError as e:
        wait_seconds = e.seconds
        print(f"FloodWaitError when updating response: {wait_seconds} seconds wait required")
        
        error_msg = f"Response was generated but Telegram rate limits were hit. Please try again in {wait_seconds} seconds."
        await safe_send_message(thinking_msg, error_msg, event=event)
        
    except Exception as e:
        error_msg = f"Sorry, an error occurred: {str(e)}"
        await safe_send_message(thinking_msg, error_msg, event=event)
        
        print(f"Error in {provider} handler: {str(e)}")

async def safe_send_message(message_obj, text, event=None, parse_mode=None):
    try:
        await message_obj.edit(text, parse_mode=parse_mode)
        return True
    except FloodWaitError as e:
        print(f"FloodWaitError in safe_send_message: {e.seconds}s wait required")
        
        if e.seconds <= 60:
            try:
                print(f"Waiting {e.seconds} seconds before retry...")
                await asyncio.sleep(e.seconds)
                await message_obj.edit(text[:4000], parse_mode=parse_mode)
                return True
            except Exception as retry_e:
                print(f"Failed to edit message after waiting: {retry_e}")
        
        if event is not None:
            try:
                await event.reply(f"⚠️ Rate limited. {text[:3900]}...", parse_mode=parse_mode)
                return True
            except Exception as reply_e:
                print(f"Failed to send new message: {reply_e}")
                
        return False
        
    except Exception as e:
        print(f"Error in safe_send_message: {e}")
        
        if event is not None:
            try:
                await event.reply(f"⚠️ Error sending message: {text[:3900]}...", parse_mode=parse_mode)
                return True
            except:
                pass
                
        return False

@client.on(events.NewMessage(pattern=r'^/hi_dog($|\s+.*)'))
async def dog_handler(event):
    await event.reply('Woof! Hello there! 🐶')

@client.on(events.NewMessage(pattern=r'^/r1 (.+)'))
async def deepseek_r1_api_handler(event):
    prompt = event.pattern_match.group(1).strip()
    
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
    
    try:
        if llm_client.environment.lower() == 'test':
            test_task = asyncio.create_task(asyncio.to_thread(llm_client.call_test, prompt))
            response = await animated_thinking(thinking_msg, test_task)
            await safe_send_message(thinking_msg, response)
            return
            
        model = "deepseek-coder-33b-instruct"
        stream_generator = llm_client.call_deepseek_stream(prompt, model=model, mode="reasoner")
        
        await process_stream_with_updates(thinking_msg, stream_generator)
            
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
            
        print(f"Error in deepseek_r1_api_handler: {str(e)}")

@client.on(events.NewMessage(pattern=r'^/unwire(?:\s+(.+))?$'))
async def unwire_news_handler(event):
    try:
        args = event.pattern_match.group(1)
        
        # Use consistent message style with animation like other commands
        try:
            thinking_msg = await event.reply(INITIAL_MESSAGE_ART)
        except FloodWaitError as e:
            print(f"FloodWaitError with art message: {e.seconds} seconds wait required. Using simple message instead.")
            await asyncio.sleep(2)
            thinking_msg = await event.reply(SIMPLE_INITIAL_MESSAGE)
        except Exception as e:
            print(f"Error sending initial message: {e}. Using simple message instead.")
            thinking_msg = await event.reply(SIMPLE_INITIAL_MESSAGE)
        
        if not args:
            # Default behavior - fetch TODAY'S news (not recent news)
            news_task = asyncio.create_task(
                asyncio.to_thread(fetch_unwire_news)  # No date parameter = today's news
            )
            news_summary = await animated_thinking(thinking_msg, news_task)
        elif args and (args.strip().startswith('http') or 'unwire.hk' in args.strip()):
            # URL provided - fetch specific article
            article_url = args.strip()
            
            # Process in a separate thread to avoid blocking
            article_task = asyncio.create_task(
                asyncio.to_thread(fetch_unwire_article, article_url)
            )
            news_summary = await animated_thinking(thinking_msg, article_task)
        elif re.match(r'^(\d{4}[-/]\d{2}[-/]\d{2})$', args.strip()):
            # Date-specific news fetch
            date_str = args.strip()
            
            # Process in a separate thread to avoid blocking
            news_task = asyncio.create_task(
                asyncio.to_thread(fetch_unwire_news, date=date_str)
            )
            news_summary = await animated_thinking(thinking_msg, news_task)
        else:
            # Check if user specified a custom days range as a number
            if args.strip().isdigit():
                days = min(int(args.strip()), 30)  # Limit to 30 days max
                
                # Process in a separate thread to avoid blocking
                news_task = asyncio.create_task(
                    asyncio.to_thread(fetch_unwire_recent, days=days)
                )
                news_summary = await animated_thinking(thinking_msg, news_task)
            else:
                # Unknown argument format
                news_summary = ("Invalid command format. Please use one of the following:\n"
                               "/unwire - Get today's news\n"
                               "/unwire 7 - Get news from the past 7 days\n"
                               "/unwire 2025-04-15 - Get news from a specific date\n"
                               "/unwire https://unwire.hk/article-url - Get a specific article")
                await thinking_msg.edit(news_summary)
                return
        
        # Check if the message is empty (no news found)
        if news_summary.startswith("No news found") or news_summary.startswith("Article not found"):
            await safe_send_message(thinking_msg, news_summary)
            return
            
        # Handle message length limits
        final_messages = []  # Track all messages sent for deletion
        TELEGRAM_MAX_LENGTH = 4000
        if len(news_summary) > TELEGRAM_MAX_LENGTH:
            first_part = news_summary[:TELEGRAM_MAX_LENGTH - 30] + "...\n\n[Message continued in replies]"
            await safe_send_message(thinking_msg, first_part)
            final_messages.append(thinking_msg)
            
            remaining_text = news_summary[TELEGRAM_MAX_LENGTH - 30:]
            chunk_size = TELEGRAM_MAX_LENGTH - 20
            
            total_parts = (len(remaining_text) + chunk_size - 1) // chunk_size
            current_part = 1
            
            while remaining_text:
                current_chunk = remaining_text[:chunk_size]
                remaining_text = remaining_text[chunk_size:]
                
                part_header = f"[Part {current_part}/{total_parts}]\n\n"
                reply_msg = await thinking_msg.respond(part_header + current_chunk)
                final_messages.append(reply_msg)
                current_part += 1
                
                await asyncio.sleep(1.5)
        else:
            await safe_send_message(thinking_msg, news_summary)
            final_messages.append(thinking_msg)

        # Schedule deletion of all news messages after 5 minutes (300 seconds)
        # First, send a notice that messages will be auto-deleted
        notice_msg = await event.respond("📢 These news messages will be automatically deleted in 5 minutes to keep the chat clean.")
        final_messages.append(notice_msg)
        
        # Schedule deletion task
        asyncio.create_task(delete_messages_after_delay(final_messages, 300))
            
    except Exception as e:
        error_msg = f"Sorry, an error occurred while fetching news: {str(e)}"
        await event.reply(error_msg)
        print(f"Error in unwire_news_handler: {str(e)}")

async def delete_messages_after_delay(messages, delay_seconds):
    """
    Delete a list of messages after the specified delay
    
    Args:
        messages: List of message objects to delete
        delay_seconds: Number of seconds to wait before deleting
    """
    try:
        # Wait for the specified time
        await asyncio.sleep(delay_seconds)
        
        # Delete all messages
        for msg in messages:
            try:
                await msg.delete()
                # Small delay between deletions to avoid rate limits
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"Error deleting message: {str(e)}")
        
        print(f"Successfully deleted {len(messages)} news messages after {delay_seconds} seconds")
    except Exception as e:
        print(f"Error in delete_messages_after_delay: {str(e)}")

async def process_stream_with_updates(message, stream_generator):
    full_response = ""
    last_update_time = 0
    min_update_interval = 3.0
    consecutive_errors = 0
    max_consecutive_errors = 3
    
    TELEGRAM_MAX_LENGTH = 4000
    
    try:
        all_chunks = []
        error_occurred = False
        response_too_long = False
        
        async for chunk in async_generator_from_sync(stream_generator):
            if isinstance(chunk, str) and (chunk.startswith("Error") or chunk.startswith("Grok API returned error")):
                error_message = f"Sorry, there was an issue with the API: {chunk}"
                await safe_send_message(message, error_message[:TELEGRAM_MAX_LENGTH])
                error_occurred = True
                break
            
            all_chunks.append(chunk)
            
            full_response = chunk
            
            if len(full_response) > TELEGRAM_MAX_LENGTH:
                response_too_long = True
                continue
            
            current_time = asyncio.get_event_loop().time()
            time_since_last_update = current_time - last_update_time
            
            if time_since_last_update >= min_update_interval and not response_too_long:
                try:
                    display_text = full_response + "\n\nTyping..."
                    
                    if len(display_text) > TELEGRAM_MAX_LENGTH:
                        display_text = display_text[:TELEGRAM_MAX_LENGTH - 30] + "...\n\n[Message continues]"
                    
                    await message.edit(display_text)
                    last_update_time = current_time
                    consecutive_errors = 0
                    
                except FloodWaitError as e:
                    consecutive_errors += 1
                    wait_seconds = getattr(e, 'seconds', 15)
                    
                    print(f"FloodWaitError in stream update: {wait_seconds}s wait required")
                    
                    min_update_interval = max(min_update_interval * 1.5, wait_seconds / 5)
                    print(f"Increasing minimum update interval to {min_update_interval}s")
                    
                    if consecutive_errors >= max_consecutive_errors:
                        print(f"Too many consecutive FloodWaitErrors ({consecutive_errors}). Stopping intermediate updates.")
                        break
                        
                    await asyncio.sleep(min(5, wait_seconds / 10))
                    
                except Exception as e:
                    print(f"Error updating message with stream chunk: {str(e)}")
        
        if all_chunks and not error_occurred:
            final_response = all_chunks[-1]
            
            if len(final_response) > TELEGRAM_MAX_LENGTH:
                print(f"Final response length: {len(final_response)} characters - splitting into multiple messages")
                
                first_part = final_response[:TELEGRAM_MAX_LENGTH - 30] + "...\n\n[Message continued in replies]"
                await safe_send_message(message, first_part)
                
                remaining_text = final_response[TELEGRAM_MAX_LENGTH - 30:]
                chunk_size = TELEGRAM_MAX_LENGTH - 20
                
                total_parts = (len(remaining_text) + chunk_size - 1) // chunk_size
                current_part = 1
                
                while remaining_text:
                    current_chunk = remaining_text[:chunk_size]
                    remaining_text = remaining_text[chunk_size:]
                    
                    part_header = f"[Part {current_part}/{total_parts}]\n\n"
                    await message.respond(part_header + current_chunk)
                    current_part += 1
                    
                    await asyncio.sleep(1.5)
            else:
                await safe_send_message(message, final_response)
        elif not error_occurred:
            await safe_send_message(message, "Sorry, the API didn't return any response. Please try again later.")
            
    except Exception as e:
        print(f"Error in process_stream_with_updates: {str(e)}")
        await safe_send_message(message, f"Error processing stream: {str(e)}")

async def show_limited_thinking_animation(message, max_updates=5, interval=15):
    animation_frames = THINKING_ANIMATIONS
    for i in range(max_updates):
        try:
            dots = (i % 3) + 1
            thinking_text = "Thinking" + "." * dots + "\n\n"
            
            current_frame = thinking_text + animation_frames[i % len(animation_frames)]
            await message.edit(current_frame)
            
            await asyncio.sleep(interval)
        except FloodWaitError as e:
            print(f"FloodWaitError in limited animation: waiting {e.seconds} seconds")
            await asyncio.sleep(e.seconds + 5)
        except asyncio.CancelledError:
            return
        except Exception as e:
            print(f"Error in limited thinking animation: {str(e)}")

async def process_stream_without_updates(stream_generator):
    full_response = ""
    try:
        async for chunk in async_generator_from_sync(stream_generator):
            if chunk.startswith("Error") or chunk.startswith("DeepSeek API returned error"):
                return f"Sorry, there was an issue with the DeepSeek API: {chunk}"
                
            full_response = chunk
            
        TELEGRAM_MAX_LENGTH = 4080
        
        if full_response:
            if len(full_response) > TELEGRAM_MAX_LENGTH:
                truncated_response = full_response[:TELEGRAM_MAX_LENGTH - 70]
                return truncated_response + "\n\n[Response truncated to fit Telegram's 4080 character limit]"
            return full_response
        else:
            return "Sorry, the API didn't return any response. Please try again later."
    except Exception as e:
        return f"Error processing stream: {str(e)}"

async def async_generator_from_sync(sync_gen):
    loop = asyncio.get_running_loop()
    for item in sync_gen:
        yield item
        await asyncio.sleep(0.01)

@client.on(events.NewMessage(pattern=r'^/deepseek (.+)'))
async def deepseek_api_handler(event):
    prompt = event.pattern_match.group(1).strip()
    
    try:
        thinking_msg = await event.reply(INITIAL_MESSAGE_ART)
    except FloodWaitError as e:
        print(f"FloodWaitError with art message: {e.seconds} seconds wait required. Using simple message instead.")
        await asyncio.sleep(2)
        thinking_msg = await event.reply(SIMPLE_INITIAL_MESSAGE)
    except Exception as e:
        print(f"Error sending initial message: {e}. Using simple message instead.")
        thinking_msg = await event.reply(SIMPLE_INITIAL_MESSAGE)
    
    response = None
    
    try:
        if llm_client.environment.lower() == 'test':
            test_task = asyncio.create_task(asyncio.to_thread(llm_client.call_test, prompt))
            response = await animated_thinking(thinking_msg, test_task)
            await safe_send_message(thinking_msg, response)
            return
        
        deepseek_task = asyncio.create_task(
            asyncio.to_thread(llm_client.call_deepseek, prompt)
        )
        
        response = await animated_thinking(thinking_msg, deepseek_task)
        
        await safe_send_message(thinking_msg, response)
        
    except FloodWaitError as e:
        wait_seconds = e.seconds
        print(f"FloodWaitError when updating response: {wait_seconds} seconds wait required")
        
        error_msg = f"Response was generated but Telegram rate limits were hit. Please try again in {wait_seconds} seconds."
        if response:
            short_resp = response[:500] + "... [truncated due to rate limits]"
            await safe_send_message(thinking_msg, short_resp, event=event)
        else:
            await safe_send_message(thinking_msg, error_msg, event=event)
            
    except Exception as e:
        error_msg = f"Sorry, an error occurred: {str(e)}"
        await safe_send_message(thinking_msg, error_msg, event=event)
            
        print(f"Error in deepseek_api_handler: {str(e)}")

@client.on(events.NewMessage(pattern=r'^/gpt (.+)'))
async def github_api_handler(event):
    prompt = event.pattern_match.group(1).strip()
    await handle_llm_request(event, 'github', prompt, system_prompt="You are a helpful AI assistant.", display_name="GitHub model")

@client.on(events.NewMessage(pattern=r'^/grok (.+)'))
async def grok_api_handler(event):
    prompt = event.pattern_match.group(1).strip()
    await handle_llm_request(event, 'grok', prompt, system_prompt="You are a helpful AI assistant.", display_name="Grok")

@client.on(events.NewMessage(pattern=r'^/grok_think (.+)'))
async def grok_think_api_handler(event):
    prompt = event.pattern_match.group(1).strip()
    await handle_grok3_stream_request(event, prompt)

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
    
    try:
        if llm_client.environment.lower() == 'test':
            test_task = asyncio.create_task(asyncio.to_thread(llm_client.call_test, prompt))
            response = await animated_thinking(thinking_msg, test_task)
            await safe_send_message(thinking_msg, response)
            return
            
        model = "grok-3-reasoner"
        system_prompt = "You are a helpful AI assistant with reasoning capabilities. Think through problems step by step and explore different aspects of the question. Format your response using HTML tags for better presentation. Use <h1>, <h2>, <h3> for headings, <p> for paragraphs, <ul> and <li> for lists, <b> for bold text, <i> for italics, and <code> for code blocks. Ensure your HTML formatting is clean and valid."
        stream_generator = llm_client.call_grok3_stream(system_prompt, prompt, model_name=model)
        
        await process_stream_with_updates(thinking_msg, stream_generator)
            
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

@client.on(events.NewMessage(pattern=r'^/env'))
async def check_environment(event):
    current_env = llm_client.environment
    env_file_setting = os.getenv('ENVIRONMENT')
    
    await event.reply(f"Current environment: {current_env}\n")

async def split_and_send_long_message(original_msg, header, content, parse_mode=None):
    TELEGRAM_MAX_LENGTH = 4000
    chunk_size = TELEGRAM_MAX_LENGTH - 20
    
    total_parts = (len(content) + chunk_size - 1) // chunk_size
    
    first_chunk = content[:chunk_size]
    await original_msg.respond(f"{header}\n\n{first_chunk}", parse_mode=parse_mode)
    
    remaining = content[chunk_size:]
    current_part = 2
    
    while remaining:
        current_chunk = remaining[:chunk_size]
        remaining = remaining[chunk_size:]
        
        part_header = f"{header} (Part {current_part}/{total_parts})"
        await original_msg.respond(f"{part_header}\n\n{current_chunk}", parse_mode=parse_mode)
        current_part += 1
        
        await asyncio.sleep(1.5)

@client.on(events.NewMessage(pattern=r'^/different (.+)'))
async def different_models_handler(event):
    prompt = event.pattern_match.group(1).strip()
    
    r1_msg = await event.respond("<b>Deepseek R1 Output:</b>\n\nLoading...", parse_mode='html')
    grok_msg = await event.respond("<b>Grok3-Think Model Output:</b>\n\nLoading...", parse_mode='html')
    analysis_msg = await event.respond("<b>Model Comparison Analysis(GPT-4o):</b>\n\nLoading...", parse_mode='html')
    
    asyncio.create_task(process_different_responses(prompt, r1_msg, grok_msg, analysis_msg))

async def process_different_responses(prompt, r1_msg, grok_msg, analysis_msg):
    responses = {}
    
    if llm_client.environment.lower() == 'test':
        test_response = "This is a test response. In test mode, we simulate model responses with this message."
        
        await safe_send_message(r1_msg, f"<b>Deepseek R1 Output:</b>\n\n{test_response}", parse_mode='html')
        await safe_send_message(grok_msg, f"<b>Grok Think Output:</b>\n\n{test_response}", parse_mode='html')
        await safe_send_message(analysis_msg, f"<b>Model Comparison Analysis:</b>\n\nTest analysis comparing the two identical responses.", parse_mode='html')
        return
    
    try:
        model = "deepseek-coder-33b-instruct"
        
        r1_generator = llm_client.call_deepseek_stream(prompt, model=model, mode="reasoner")
        
        r1_response = await process_stream_without_updates(r1_generator)
        responses['r1'] = r1_response
        
        TELEGRAM_MAX_LENGTH = 4000
        if len(r1_response) > TELEGRAM_MAX_LENGTH:
            truncated = r1_response[:TELEGRAM_MAX_LENGTH - 50] + "...\n\n[Response too long, full response will be sent as replies]"
            await safe_send_message(r1_msg, f"<b>R1 Output:</b>\n\n{truncated}", parse_mode='html')
            await split_and_send_long_message(r1_msg, "<b>R1 Output (continued):</b>", r1_response, parse_mode='html')
        else:
            await safe_send_message(r1_msg, f"<b>R1 Output:</b>\n\n{r1_response}", parse_mode='html')
    except Exception as e:
        print(f"Error getting R1 response: {str(e)}")
        await safe_send_message(r1_msg, f"<b>R1 Output Error:</b>\n\n{str(e)}", parse_mode='html')
        responses['r1'] = f"Error: {str(e)}"
    
    try:
        model = "grok-3-reasoner"
        system_prompt = "You are a helpful AI assistant with reasoning capabilities. Think through problems step by step and explore different aspects of the question. IMPORTANT: Your response MUST NOT exceed 3800 characters in length. If you find yourself approaching this limit, summarize remaining information concisely."
        
        grok_generator = llm_client.call_grok3_stream(system_prompt, prompt, model_name=model)
        
        grok_response = await process_stream_without_updates(grok_generator)
        responses['grok'] = grok_response
        
        GROK_MAX_LENGTH = 3999
        
        if len(grok_response) > GROK_MAX_LENGTH:
            truncated_grok = grok_response[:GROK_MAX_LENGTH - 50] + "...\n\n[Response truncated to 3800 characters]"
            await safe_send_message(grok_msg, f"<b>Grok Think Output:</b>\n\n{truncated_grok}", parse_mode='html')
            responses['grok'] = truncated_grok
        else:
            await safe_send_message(grok_msg, f"<b>Grok Think Output:</b>\n\n{grok_response}", parse_mode='html')
    except Exception as e:
        print(f"Error getting Grok Think response: {str(e)}")
        await safe_send_message(grok_msg, f"<b>Grok Think Output Error:</b>\n\n{str(e)}", parse_mode='html')
        responses['grok'] = f"Error: {str(e)}"
    
    if 'r1' in responses and 'grok' in responses and not (responses['r1'].startswith('Error') or responses['grok'].startswith('Error')):
        try:
            system_prompt = """
            You are an AI comparison expert. You will be provided with:
            1. A user's question
            2. Response from Model A (R1)
            3. Response from Model B (Grok)
            
            Your task is to:
            1. Compare the responses objectively
            2. Assess the similarity of the two LLM model outputs (0-100%)
             3. Provide a brief summary of the differences
            4. Identify strengths and weaknesses in each response
            5. Determine which model provided the more comprehensive or accurate response

            Format your analysis with clear sections and be impartial in your evaluation.
            """
            
            user_prompt = f"""
            USER QUESTION:
            {prompt}
            
            MODEL A (R1) RESPONSE:
            {responses['r1']}
            
            MODEL B (GROK) RESPONSE:
            {responses['grok']}
            """
            
            comparison_result = await asyncio.to_thread(
                llm_client.call_github, 
                system_prompt, 
                user_prompt,
                model_name="gpt-4o-mini"
            )
            
            ANALYSIS_MAX_LENGTH = 4000
            if len(comparison_result) > ANALYSIS_MAX_LENGTH:
                truncated = comparison_result[:ANALYSIS_MAX_LENGTH - 50] + "...\n\n[Analysis too long, full analysis will be sent as replies]"
                await safe_send_message(analysis_msg, f"<b>Model Comparison Analysis(ChatGPT-4o):</b>\n\n{truncated}", parse_mode='html')
                await split_and_send_long_message(analysis_msg, "<b>Model Comparison Analysis (continued):</b>", comparison_result, parse_mode='html')
            else:
                await safe_send_message(analysis_msg, f"<b>Model Comparison Analysis(ChatGPT-4o):</b>\n\n{comparison_result}", parse_mode='html')
                
        except Exception as e:
            print(f"Error getting comparison analysis: {str(e)}")
            await safe_send_message(analysis_msg, f"<b>Model Comparison Analysis Error:</b>\n\nUnable to generate comparison: {str(e)}", parse_mode='html')
    else:
        await safe_send_message(analysis_msg, f"<b>Model Comparison Analysis:</b>\n\nUnable to generate comparison because one or both models returned an error.", parse_mode='html')

async def main():
    environment = os.getenv('ENVIRONMENT')
    print(f"Starting userbot in {environment.upper()} mode...")
    
    await client.start(phone=PHONE_NUMBER)
    print("Userbot is running...")
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())