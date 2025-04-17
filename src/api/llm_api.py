import os
import requests
import json
import time
import sys
from dotenv import load_dotenv
import toml
from openai import OpenAI

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

# Load environment variables from config/.env file
load_dotenv(os.path.join(os.path.dirname(parent_dir), 'config', '.env'))

class LLMClient:
    """
    A client for interacting with various LLM APIs
    """
    
    def __init__(self):
        """
        Initialize the LLM client with API keys from environment variables
        """
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.deepseek_api_key = os.getenv('DEEPSEEK_API_KEY')
        self.github_api_key = os.getenv('GITHUB_API_KEY')
        self.grok_api_key = os.getenv('GROK_API_KEY')
        self.environment = os.getenv('ENVIRONMENT', 'test') 
        
        # Load API keys from credentials file (as fallback)
        config_dir = os.path.join(os.path.dirname(parent_dir), 'config')
        file_path = os.path.join(config_dir, 'credentials') if os.path.exists(config_dir) else 'credentials'
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                self.secrets = toml.load(f)
        else:
            # Default empty dictionary if credentials file doesn't exist
            self.secrets = {}
        
    def call_openai(self, prompt, model="gpt-3.5-turbo", max_tokens=1000):
        """
        Call the OpenAI API to generate a response
        
        Args:
            prompt (str): The prompt to send to the API
            model (str): The model to use (default: gpt-3.5-turbo)
            max_tokens (int): Maximum tokens in response (default: 1000)
            
        Returns:
            str: Generated text response
        """
        if not self.openai_api_key:
            return "OpenAI API key not found. Please set it in the .env file."
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.openai_api_key}"
        }
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens
        }
        
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return f"Error calling OpenAI API: {str(e)}"
    
    def call_deepseek(self, prompt, model="deepseek-chat", max_tokens=1000, temperature=0.7):
        """
        Call the Deepseek API to generate a response
        
        Args:
            prompt (str): The prompt to send to the API
            model (str): The model to use (default: deepseek-chat)
            max_tokens (int): Maximum tokens in response (default: 1000)
            temperature (float): Temperature for response generation (default: 0.7)
            
        Returns:
            str: Generated text response
        """
        if not self.deepseek_api_key:
            return "Deepseek API key not found. Please set it in the .env file."
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.deepseek_api_key}"
        }
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False
        }
        
        try:
            response = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return f"Error calling Deepseek API: {str(e)}"
    
    def call_deepseek_stream(self, prompt, model="", max_tokens=1000, temperature=0.7, mode="chat"):
        """
        Call the Deepseek API with streaming support to generate a response
        
        Args:
            prompt (str): The prompt to send to the API
            model (str): The model base name to use (default: deepseek-chat)
            max_tokens (int): Maximum tokens in response (default: 1000)
            temperature (float): Temperature for response generation (default: 0.7)
            mode (str): Whether to use 'chat' or 'reasoner' mode (default: chat)
            
        Returns:
            Generator: Yields chunks of the generated text response, with final complete response at the end
        """
        if not self.deepseek_api_key:
            yield "Deepseek API key not found. Please set it in the .env file."
            return
        
        # Adjust the model name based on the mode
        if mode == "reasoner":
            # DeepSeek reasoner models have specific IDs - use the correct model ID directly
            model = "deepseek-coder-33b-instruct"  # This is the model that supports reasoning capabilities
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.deepseek_api_key}"
        }
        
        # Create a system message for reasoner mode
        messages = []
        if mode == "reasoner":
            messages.append({
                "role": "system", 
                "content": "You are a helpful AI assistant with reasoning capabilities. Think through problems step by step."
            })
            model = "deepseek-reasoner"
        
        # Add the user message
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True
        }
        
        try:
            # Print request details for debugging
            print(f"Making request to DeepSeek API with model: {model}")
            
            # Stream the response
            response = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers=headers,
                json=payload,
                stream=True
            )
            
            # Check for errors before processing
            if response.status_code != 200:
                error_msg = f"DeepSeek API returned error {response.status_code}"
                try:
                    error_json = json.loads(response.content.decode('utf-8'))
                    if 'error' in error_json:
                        error_msg += f": {error_json['error']['message']}"
                except:
                    error_msg += f": {response.text}"
                
                yield error_msg
                return
            
            collected_content = ""
            final_content = ""
            
            for line in response.iter_lines():
                if line:
                    # Skip the "data: " prefix
                    line = line.decode('utf-8')
                    if line.startswith("data: "):
                        line = line[6:]  # Skip "data: "
                    
                    # Check for [DONE] message
                    if line == "[DONE]":
                        # Make sure to yield the final complete response one last time
                        if final_content:
                            yield final_content
                        break
                    
                    try:
                        json_response = json.loads(line)
                        # Extract the content - may differ based on the actual Deepseek API response format
                        if "choices" in json_response and json_response["choices"]:
                            delta = json_response["choices"][0].get("delta", {})
                            if "content" in delta and delta["content"]:
                                collected_content += delta["content"]
                                # Track the complete response for final yield
                                final_content = collected_content
                                yield collected_content
                    except json.JSONDecodeError:
                        # Skip lines that can't be decoded as JSON
                        pass
                        
            # Ensure final response is yielded one last time after stream is complete
            # This helps prevent bugs with incomplete responses
            if final_content:
                yield final_content
                
        except Exception as e:
            yield f"Error streaming from Deepseek API: {str(e)}"
    
    def call_github(self, system_prompt, user_prompt, model_name="gpt-4o-mini"):
        """
        Call the GitHub API to generate a response
        
        Args:
            system_prompt (str): The system prompt to set context
            user_prompt (str): The user prompt to send to the API
            model_name (str): The model to use (default: gpt-4o-mini)
            
        Returns:
            str: Generated text response
        """
        endpoint = "https://models.inference.ai.azure.com"
        
        # First try to get API key from environment variables
        github_api_key = os.getenv('GITHUB_API_KEY')
            
        if not github_api_key:
            return "GitHub API key not found. Please set it in the .env file or credentials file."
        
        client = OpenAI(
            base_url=endpoint,
            api_key=github_api_key,
        )

        try:
            response = client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    }
                ],
                temperature=1.0,
                top_p=1.0,
                max_tokens=1000,
                model=model_name
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error calling GitHub API: {str(e)}"
    
    def call_grok3(self, system_prompt, user_prompt, model_name="grok-3"):
        """
        Call the Grok3 API to generate a response
        
        Args:
            system_prompt (str): The system prompt to set context
            user_prompt (str): The user prompt to send to the API
            model_name (str): The model to use (default: grok-3, can be grok-3-reasoner, grok-3-deepsearch)
            
        Returns:
            str: Generated text response
        """
        # Try to get API key from environment variables first
        grok_api_key = self.grok_api_key
         
        if not grok_api_key:
            return "Grok API key not found. Please set GROK_API_KEY in the .env file or credentials file."
        
        # 移除 HTML 格式要求，改為使用 Telegram 友好的格式
        enhanced_system_prompt = system_prompt
        if system_prompt and not "Format your response" in system_prompt:
            enhanced_system_prompt = system_prompt + " Format your response clearly with proper spacing, line breaks, and structure. Use markdown-style formatting like *bold*, _italic_, and `code` for emphasis. Use numbered lists (1., 2., 3.) and bullet points (- or *) for lists. Ensure your response is well-structured and easy to read."
        elif not system_prompt:
            enhanced_system_prompt = "You are a helpful AI assistant. Format your response clearly with proper spacing, line breaks, and structure. Use markdown-style formatting like *bold*, _italic_, and `code` for emphasis. Use numbered lists (1., 2., 3.) and bullet points (- or *) for lists. Ensure your response is well-structured and easy to read."
        
        # Based on common OpenAI-compatible API patterns
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {grok_api_key}"
        }
        
        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "system",
                    "content": enhanced_system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        # Using the correct endpoint from API documentation
        api_url = "https://chatapi.littlewheat.com/v1/chat/completions"
        
        try:
            response = requests.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return f"Error calling Grok API: {str(e)}"
    
    def call_grok3_client(self, system_prompt, user_prompt, model_name="grok-3-reasoner"):
        """
        Call the Grok3 API using OpenAI client to generate a response
        
        Args:
            system_prompt (str): The system prompt to set context
            user_prompt (str): The user prompt to send to the API
            model_name (str): The model to use (default: grok-3)
            
        Returns:
            str: Generated text response
        """
        # Try to get API key from environment variables first
        grok_api_key = self.grok_api_key
              
        if not grok_api_key:
            return "Grok API key not found. Please set GROK_API_KEY in the .env file or credentials file."
        
        # 移除 HTML 格式要求，改為使用 Telegram 友好的格式
        enhanced_system_prompt = system_prompt
        if system_prompt and not "Format your response" in system_prompt:
            enhanced_system_prompt = system_prompt + " Format your response clearly with proper spacing, line breaks, and structure. Use markdown-style formatting like *bold*, _italic_, and `code` for emphasis. Use numbered lists (1., 2., 3.) and bullet points (- or *) for lists. Ensure your response is well-structured and easy to read."
        elif not system_prompt:
            enhanced_system_prompt = "You are a helpful AI assistant. Format your response clearly with proper spacing, line breaks, and structure. Use markdown-style formatting like *bold*, _italic_, and `code` for emphasis. Use numbered lists (1., 2., 3.) and bullet points (- or *) for lists. Ensure your response is well-structured and easy to read."
        
        client = OpenAI(
            base_url="https://chatapi.littlewheat.com/v1",
            api_key=grok_api_key,
        )

        try:
            response = client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": enhanced_system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    }
                ],
                temperature=0.7,
                top_p=1.0,
                max_tokens=1000,
                model=model_name
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error calling Grok API: {str(e)}"
    
    def call_grok3_http(self, system_prompt, user_prompt, model_name="grok-3"):
        """
        Call the Grok3 API using http.client to generate a response
        
        Args:
            system_prompt (str): The system prompt to set context
            user_prompt (str): The user prompt to send to the API
            model_name (str): The model to use (default: grok-3)
            
        Returns:
            str: Generated text response
        """
        import http.client
        import json
        
        try:
            # Get API key from environment variables
            grok_api_key = self.grok_api_key
            
            if not grok_api_key:
                return "Grok API key not found. Please set GROK_API_KEY in the .env file or credentials file."
            
            # 移除 HTML 格式要求，改為使用 Telegram 友好的格式
            enhanced_system_prompt = system_prompt
            if system_prompt and not "Format your response" in system_prompt:
                enhanced_system_prompt = system_prompt + " Format your response clearly with proper spacing, line breaks, and structure. Use markdown-style formatting like *bold*, _italic_, and `code` for emphasis. Use numbered lists (1., 2., 3.) and bullet points (- or *) for lists. Ensure your response is well-structured and easy to read."
            elif not system_prompt:
                enhanced_system_prompt = "You are a helpful AI assistant. Format your response clearly with proper spacing, line breaks, and structure. Use markdown-style formatting like *bold*, _italic_, and `code` for emphasis. Use numbered lists (1., 2., 3.) and bullet points (- or *) for lists. Ensure your response is well-structured and easy to read."
            
            # Setup messages with enhanced system prompt
            messages = []
            if enhanced_system_prompt:
                messages.append({
                    "role": "system",
                    "content": enhanced_system_prompt
                })
            
            # Add user message
            messages.append({
                "role": "user", 
                "content": user_prompt
            })
            
            # Setup the HTTP connection to the API endpoint
            conn = http.client.HTTPSConnection("chatapi.littlewheat.com")
            
            # Prepare the request payload
            payload = json.dumps({
                "model": model_name,
                "messages": messages,
                "stream": False,
                "temperature": 0.7,
                "max_tokens": 1000
            })
            
            # Set headers with authorization
            headers = {
                'Authorization': f'Bearer {grok_api_key}',
                'Content-Type': 'application/json'
            }
            
            # Send the request
            conn.request("POST", "/v1/chat/completions", payload, headers)
            
            # Get the response
            res = conn.getresponse()
            data = res.read()
            
            # Parse the response
            if res.status != 200:
                return f"Error calling Grok API: HTTP status {res.status} - {data.decode('utf-8')}"
                
            response_data = json.loads(data.decode("utf-8"))
            return response_data["choices"][0]["message"]["content"]
            
        except Exception as e:
            return f"Error calling Grok API with HTTP client: {str(e)}"
    
    def call_grok3_stream(self, system_prompt, user_prompt, model_name="grok-3-reasoner"):
        """
        Call the Grok3 API with streaming support to generate a response
        
        Args:
            system_prompt (str): The system prompt to set context
            user_prompt (str): The user prompt to send to the API
            model_name (str): The model to use (default: grok-3-reasoner)
            
        Returns:
            Generator: Yields chunks of the generated text response, with final complete response at the end
        """
        import http.client
        import json
        import time
        import socket
        
        # Get API key from environment variables
        grok_api_key = self.grok_api_key
        
        if not grok_api_key:
            yield "Grok API key not found. Please set GROK_API_KEY in the .env file or credentials file."
            return
        
        # 移除 HTML 格式要求，改為使用純文本格式
        enhanced_system_prompt = system_prompt
        if system_prompt and not "Format your response" in system_prompt:
            enhanced_system_prompt = system_prompt + " Format your response clearly with proper spacing, line breaks, and structure. Use markdown-style formatting like *bold*, _italic_, and `code` for emphasis. Use numbered lists (1., 2., 3.) and bullet points (- or *) for lists. Ensure your response is well-structured and easy to read."
        elif not system_prompt:
            enhanced_system_prompt = "You are a helpful AI assistant. Format your response clearly with proper spacing, line breaks, and structure. Use markdown-style formatting like *bold*, _italic_, and `code` for emphasis. Use numbered lists (1., 2., 3.) and bullet points (- or *) for lists. Ensure your response is well-structured and easy to read."
        
        # Setup messages with enhanced system prompt
        messages = []
        if enhanced_system_prompt:
            messages.append({
                "role": "system",
                "content": enhanced_system_prompt
            })
        
        # Add user message
        messages.append({
            "role": "user", 
                "content": user_prompt
        })
        
        # Maximum number of retries
        max_retries = 5  # 增加最大重試次數
        retry_count = 0
        retry_delay = 2  # seconds
        
        while retry_count < max_retries:
            try:
                # Print request details for debugging
                print(f"Making request to chatapi.littlewheat.com with model: {model_name} (attempt {retry_count + 1}/{max_retries})")
                print(f"Messages: {messages}")

                # 使用更長的超時時間
                socket.setdefaulttimeout(120)  # 設置全局套接字超時為120秒
                # Setup connection to the specific API endpoint with longer timeout
                conn = http.client.HTTPSConnection("chatapi.littlewheat.com", timeout=120)
                
                # Prepare payload for streaming
                payload = json.dumps({
                    "model": model_name,  # Use grok-3-reasoner directly
                    "messages": messages,
                    "stream": True,
                    "temperature": 0.7,
                    "max_tokens": 1000
                })
                
                # Set headers with the API key
                headers = {
                    'Authorization': f'Bearer {grok_api_key}',
                    'Content-Type': 'application/json'
                }
                
                # Make the streaming API request
                conn.request("POST", "/v1/chat/completions", payload, headers)
                response = conn.getresponse()
                
                # Check for errors
                if response.status != 200:
                    error_data = response.read().decode('utf-8', errors='replace')
                    error_msg = f"Grok API returned error {response.status}: {error_data}"
                    
                    # If it's a server error (5xx), retry
                    if 500 <= response.status < 600:
                        retry_count += 1
                        if retry_count < max_retries:
                            print(f"Server error {response.status}, retrying in {retry_delay} seconds... (attempt {retry_count+1}/{max_retries})")
                            time.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                            continue
                    
                    # If we've exhausted retries or it's a client error, yield the error message
                    yield error_msg
                    return
                
                # Process the streaming response
                collected_content = ""
                buffer = ""
                last_activity_time = time.time()
                activity_timeout = 60  # 60秒無活動超時
                
                # Read larger chunks instead of byte-by-byte to avoid UTF-8 decoding issues
                while True:
                    # 檢查無活動超時
                    if time.time() - last_activity_time > activity_timeout:
                        print(f"No activity from Grok API for {activity_timeout} seconds, closing connection")
                        break
                    
                    try:
                        chunk = response.read(4096)  # Read 4KB at a time
                        if not chunk:
                            break
                        
                        # 更新上次活動時間
                        last_activity_time = time.time()
                        
                        # Decode with error handling
                        try:
                            text = chunk.decode('utf-8', errors='replace')
                            buffer += text
                        except Exception as e:
                            print(f"Warning: Error decoding chunk: {e}")
                            continue
                        
                        # Process complete lines
                        while '\n' in buffer:
                            pos = buffer.find('\n')
                            line = buffer[:pos]
                            buffer = buffer[pos + 1:]
                            
                            if not line.strip():
                                continue
                            
                            if line.startswith('data: '):
                                line = line[6:].strip()  # Skip "data: " prefix
                                
                                if line == '[DONE]':
                                    # Final yield of complete response
                                    if collected_content:
                                        yield collected_content
                                    return
                                
                                try:
                                    json_response = json.loads(line)
                                    if "choices" in json_response and json_response["choices"]:
                                        delta = json_response["choices"][0].get("delta", {})
                                        if "content" in delta and delta["content"]:
                                            new_content = delta["content"]
                                            collected_content += new_content
                                            yield collected_content
                                except json.JSONDecodeError as je:
                                    print(f"Warning: JSON decode error: {je}. Input: {line[:100]}...")
                                    continue
                    except socket.timeout:
                        # 處理超時
                        print(f"Socket timeout while reading response, retrying... (attempt {retry_count+1}/{max_retries})")
                        retry_count += 1
                        if retry_count < max_retries:
                            time.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                            break  # 跳出內層循環，重新連接
                        else:
                            yield "Error: Read operation timed out after multiple attempts. Please try again later."
                            return
                
                # Process any remaining data in the buffer
                if buffer.strip():
                    for line in buffer.strip().split('\n'):
                        if line.startswith('data: '):
                            line = line[6:].strip()
                            
                            if line == '[DONE]':
                                break
                            
                            try:
                                json_response = json.loads(line)
                                if "choices" in json_response and json_response["choices"]:
                                    delta = json_response["choices"][0].get("delta", {})
                                    if "content" in delta and delta["content"]:
                                        new_content = delta["content"]
                                        collected_content += new_content
                            except json.JSONDecodeError:
                                continue
                                
                # Make sure we yield the final content
                if collected_content:
                    yield collected_content
                    return
                    
            except socket.timeout:
                print(f"Socket timeout error, retrying... (attempt {retry_count+1}/{max_retries})")
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                else:
                    yield f"Error: Connection to Grok API timed out after {max_retries} attempts. Please try again later."
                    return
                    
            except http.client.HTTPException as e:
                retry_count += 1
                if retry_count < max_retries:
                    print(f"HTTP error: {e}, retrying in {retry_delay} seconds... (attempt {retry_count+1}/{max_retries})")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                else:
                    yield f"Error connecting to Grok API after {max_retries} attempts: {str(e)}"
                    return
                    
            except Exception as e:
                import traceback
                print(f"Error streaming from Grok API: {str(e)}")
                print(traceback.format_exc())
                retry_count += 1
                if retry_count < max_retries:
                    print(f"Unexpected error, retrying in {retry_delay} seconds... (attempt {retry_count+1}/{max_retries})")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    yield f"Error streaming from Grok API after {max_retries} attempts: {str(e)}"
                    return
    
    def call_test(self, prompt=None, delay=4):
        """
        A testing interface that simulates an API call by waiting and returning a fixed response
        
        Args:
            prompt (str): The prompt (not used in this test interface, included for API consistency)
            delay (int): Number of seconds to wait before responding (default: 2)
            
        Returns:
            str: Fixed "Hello world" response after delay
        """
        # Log that a test call is being made
        print(f"Test API called with prompt: {prompt}")
        
        # Simulate API processing time
        time.sleep(delay)
        
        # Return fixed test response
        # Return a message indicating LLM service is unavailable (for testing)
        return "Hello World\nService is currently unavailable. This is a test response."
        
    def call_llm(self, provider, prompt, **kwargs):
        """
        Route LLM calls based on environment setting
        
        Args:
            provider (str): The API provider to use ('openai', 'anthropic', 'deepseek', 'github', 'openrouter', 'grok')
            prompt (str): The prompt to send to the API
            **kwargs: Additional arguments to pass to the specific API call
            
        Returns:
            str: Generated text response from the API or test response
        """
        # If in test environment, use the test API regardless of provider
        if self.environment.lower() == 'test':
            print(f"Environment is set to test, routing {provider} call to test API")
            return self.call_test(prompt)
        
        # Otherwise route to the appropriate API based on provider
        if provider == 'openai':
            return self.call_openai(prompt, **kwargs)
        elif provider == 'deepseek':
            return self.call_deepseek(prompt, **kwargs)
        elif provider == 'github':
            system_prompt = kwargs.get('system_prompt', '')
            user_prompt = prompt
            model_name = kwargs.get('model_name', 'gpt-4o-mini')
            return self.call_github(system_prompt, user_prompt, model_name)
        elif provider == 'grok':
            system_prompt = kwargs.get('system_prompt', '')
            user_prompt = prompt
            model_name = kwargs.get('model_name', 'grok-3')
            # Use the new HTTP client implementation
            return self.call_grok3_http(system_prompt, user_prompt, model_name)
        else:
            return f"Unknown provider: {provider}"

# Example usage
if __name__ == "__main__":
    client = LLMClient()
    
    # Example prompt
    prompt = "Explain quantum computing in simple terms"
    
    # Test the routing mechanism
    print("Using routing mechanism:")
    print(client.call_llm('deepseek', prompt))
    
    # Temporarily set environment to test for demonstration
    os.environ['ENVIRONMENT'] = 'test'
    client.environment = 'test'
    print("\nAfter setting environment to test:")
    print(client.call_llm('deepseek', prompt))