import http.client
import json
import time
import logging
from ..llm_client import LLMProvider

logger = logging.getLogger("grok_provider")

class GrokProvider(LLMProvider):
    """
    Implementation of Grok API provider
    """
    def __init__(self, api_key=None):
        """
        Initialize Grok provider
        
        Args:
            api_key (str, optional): Grok API key
        """
        super().__init__(api_key)
        if not self.api_key:
            logger.warning("Grok API key is not provided")
    
    def call(self, prompt, **kwargs):
        """
        Call Grok API to generate response
        
        Args:
            prompt (str): User prompt
            **kwargs: Additional parameters including:
                system_prompt (str): System prompt to set context
                model_name (str): Model to use (default: grok-3)
                
        Returns:
            str: Generated text response
        """
        system_prompt = kwargs.get('system_prompt', '')
        model_name = kwargs.get('model_name', 'grok-3')
        
        if not self.api_key:
            return "Grok API key not found. Please set GROK_API_KEY in the .env file or credentials file."
        
        # Enhance system prompt for Telegram-friendly formatting
        enhanced_system_prompt = system_prompt
        if system_prompt and "Format your response" not in system_prompt:
            enhanced_system_prompt = system_prompt + " Format your response clearly with proper spacing, line breaks, and structure. Use markdown-style formatting like *bold*, _italic_, and `code` for emphasis. Use numbered lists (1., 2., 3.) and bullet points (- or *) for lists. Ensure your response is well-structured and easy to read."
        elif not system_prompt:
            enhanced_system_prompt = "You are a helpful AI assistant. Format your response clearly with proper spacing, line breaks, and structure. Use markdown-style formatting like *bold*, _italic_, and `code` for emphasis. Use numbered lists (1., 2., 3.) and bullet points (- or *) for lists. Ensure your response is well-structured and easy to read."
        
        try:
            # Set up HTTP connection to API endpoint
            conn = http.client.HTTPSConnection("chatapi.littlewheat.com")
            
            # Set up messages
            messages = []
            if enhanced_system_prompt:
                messages.append({
                    "role": "system",
                    "content": enhanced_system_prompt
                })
            
            # Add user message
            messages.append({
                "role": "user", 
                "content": prompt
            })
            
            # Prepare request payload
            payload = json.dumps({
                "model": model_name,
                "messages": messages,
                "stream": False,
                "temperature": 0.7,
                "max_tokens": 1000
            })
            
            # Set headers with authorization
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            # Send request
            conn.request("POST", "/v1/chat/completions", payload, headers)
            
            # Get response
            res = conn.getresponse()
            data = res.read()
            
            # Parse response
            if res.status != 200:
                return f"Error calling Grok API: HTTP status {res.status} - {data.decode('utf-8')}"
                
            response_data = json.loads(data.decode("utf-8"))
            return response_data["choices"][0]["message"]["content"]
            
        except Exception as e:
            logger.error(f"Error calling Grok API: {e}")
            return f"Error calling Grok API: {str(e)}"
    
    def call_stream(self, prompt, **kwargs):
        """
        Call Grok API with streaming support to generate response
        
        Args:
            prompt (str): User prompt
            **kwargs: Additional parameters including:
                system_prompt (str): System prompt to set context
                model_name (str): Model to use (default: grok-3-reasoner)
                
        Returns:
            Generator: Generator yielding partial responses
        """
        # Get keyword arguments
        system_prompt = kwargs.get('system_prompt', '')
        model_name = kwargs.get('model_name', 'grok-3-reasoner')
        
        if not self.api_key:
            yield "Grok API key not found. Please set GROK_API_KEY in the .env file or credentials file."
            return
        
        # Enhance system prompt
        enhanced_system_prompt = system_prompt
        if system_prompt and "Format your response" not in system_prompt:
            enhanced_system_prompt = system_prompt + " Format your response clearly with proper spacing, line breaks, and structure. Use markdown-style formatting like *bold*, _italic_, and `code` for emphasis. Use numbered lists (1., 2., 3.) and bullet points (- or *) for lists. Ensure your response is well-structured and easy to read."
        elif not system_prompt:
            enhanced_system_prompt = "You are a helpful AI assistant. Format your response clearly with proper spacing, line breaks, and structure. Use markdown-style formatting like *bold*, _italic_, and `code` for emphasis. Use numbered lists (1., 2., 3.) and bullet points (- or *) for lists. Ensure your response is well-structured and easy to read."
        
        # Set up messages
        messages = []
        if enhanced_system_prompt:
            messages.append({
                "role": "system",
                "content": enhanced_system_prompt
            })
        
        # Add user message
        messages.append({
            "role": "user", 
            "content": prompt
        })
        
        # Maximum retry count
        max_retries = 3
        retry_count = 0
        retry_delay = 2  # seconds
        
        while retry_count < max_retries:
            try:
                # Print request details for debugging
                logger.info(f"Making request to chatapi.littlewheat.com with model: {model_name} (attempt {retry_count + 1}/{max_retries})")
                
                # Set up connection to specific API endpoint
                conn = http.client.HTTPSConnection("chatapi.littlewheat.com", timeout=30)
                
                # Prepare streaming payload
                payload = json.dumps({
                    "model": model_name,
                    "messages": messages,
                    "stream": True,
                    "temperature": 0.7,
                    "max_tokens": 1000
                })
                
                # Set headers with API key
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                }
                
                # Make streaming API request
                conn.request("POST", "/v1/chat/completions", payload, headers)
                response = conn.getresponse()
                
                # Check for errors
                if response.status != 200:
                    error_data = response.read().decode('utf-8', errors='replace')
                    error_msg = f"Grok API returned error {response.status}: {error_data}"
                    
                    # If server error (5xx), retry
                    if 500 <= response.status < 600:
                        retry_count += 1
                        if retry_count < max_retries:
                            logger.warning(f"Server error {response.status}, retrying in {retry_delay} seconds...")
                            time.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                            continue
                    
                    # If we've exhausted retries or it's a client error, yield error message
                    yield error_msg
                    return
                
                # Process streaming response
                collected_content = ""
                buffer = ""
                incomplete_json = ""
                
                # Read larger chunks at once instead of byte by byte to avoid UTF-8 decoding issues
                while True:
                    chunk = response.read(4096)  # Read 4KB at a time
                    if not chunk:
                        break
                    
                    # Decode with error handling
                    try:
                        text = chunk.decode('utf-8', errors='replace')
                        buffer += text
                    except Exception as e:
                        logger.warning(f"Warning: Error decoding chunk: {e}")
                        continue
                    
                    # Process complete lines
                    lines = buffer.split('\n')
                    buffer = lines.pop()  # Keep the last possibly incomplete line in the buffer
                    
                    for line in lines:
                        if not line.strip():
                            continue
                        
                        if line.startswith('data: '):
                            line = line[6:].strip()  # Skip "data: " prefix
                            
                            if line == '[DONE]':
                                # Final yield of complete response
                                if collected_content:
                                    yield collected_content
                                return
                            
                            # Improved JSON processing logic
                            try:
                                # Try direct parsing
                                json_obj = None
                                try:
                                    json_obj = json.loads(line)
                                except json.JSONDecodeError:
                                    # If there's incomplete JSON from previous chunk, try combining
                                    if incomplete_json:
                                        try:
                                            combined = incomplete_json + line
                                            json_obj = json.loads(combined)
                                            incomplete_json = ""  # Reset after successful parse
                                        except json.JSONDecodeError:
                                            # Still incomplete, store for next iteration
                                            incomplete_json += line
                                            continue
                                    else:
                                        # This might be the start of incomplete JSON
                                        incomplete_json = line
                                        continue
                                
                                # If we have successfully parsed the JSON object
                                if json_obj and "choices" in json_obj and json_obj["choices"]:
                                    delta = json_obj["choices"][0].get("delta", {})
                                    if "content" in delta and delta["content"] is not None:
                                        new_content = delta["content"]
                                        collected_content += new_content
                                        yield collected_content
                            except Exception as je:
                                logger.warning(f"Warning: JSON processing error: {je}. Input: {line[:100]}...")
                                # Do not store this as incomplete_json, as it might be invalid
                                incomplete_json = ""  # Reset invalid JSON
                                continue
                
                # Process any remaining buffer content
                if buffer.strip():
                    if buffer.startswith('data: '):
                        buffer = buffer[6:].strip()
                        
                    if buffer != '[DONE]':
                        # Try to process any remaining JSON
                        try:
                            combined = incomplete_json + buffer if incomplete_json else buffer
                            json_obj = None
                            
                            try:
                                json_obj = json.loads(combined)
                            except json.JSONDecodeError:
                                # If we still can't parse it, try to clean it up
                                # Sometimes we get broken JSON at the end of the stream
                                try:
                                    # Try to find the last complete JSON object
                                    if combined.rstrip().endswith("}"):
                                        # Find the last opening brace that might start a valid object
                                        last_open = combined.rfind("{")
                                        if last_open >= 0:
                                            # Extract what might be a valid JSON object
                                            potential_json = combined[last_open:]
                                            json_obj = json.loads(potential_json)
                                except:
                                    logger.warning(f"Warning: Could not parse final buffer content: {buffer[:100]}...")
                            
                            if json_obj and "choices" in json_obj and json_obj["choices"]:
                                delta = json_obj["choices"][0].get("delta", {})
                                if "content" in delta and delta["content"] is not None:
                                    new_content = delta["content"]
                                    collected_content += new_content
                        except Exception as e:
                            logger.warning(f"Warning: Error processing final buffer: {str(e)}")
                            
                # Ensure we generate final content
                if collected_content:
                    yield collected_content
                return
                    
            except http.client.HTTPException as e:
                retry_count += 1
                if retry_count < max_retries:
                    logger.warning(f"HTTP error: {e}, retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                else:
                    logger.error(f"HTTP error after {max_retries} attempts: {e}")
                    yield f"Error connecting to Grok API after {max_retries} attempts: {str(e)}"
                    return
                    
            except Exception as e:
                import traceback
                logger.error(f"Error streaming from Grok API: {str(e)}")
                logger.error(traceback.format_exc())
                yield f"Error streaming from Grok API: {str(e)}"
                return