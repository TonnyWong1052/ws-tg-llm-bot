import os
import json
import requests
import logging
import http.client
import time
from ..base_provider import LLMProvider

logger = logging.getLogger("llm_client")

class GrokProvider(LLMProvider):
    """
    Grok API provider implementation using chatapi.littlewheat.com endpoint
    """
    def __init__(self, api_key=None):
        """
        Initialize Grok provider
        
        Args:
            api_key (str, optional): Grok API key
        """
        super().__init__(api_key)
        self.api_key = api_key or os.getenv('GROK_API_KEY')
        # Use chatapi.littlewheat.com as the endpoint
        self.base_domain = "chatapi.littlewheat.com"
        self.endpoint = "/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def log_request(self, prompt, model, system_prompt):
        """
        Log the details of the API request
        
        Args:
            prompt (str): The user prompt
            model (str): The model being used
            system_prompt (str): The system prompt, if any
        """
        logger.info(f"Requesting Grok API with model: {model}")
        logger.debug(f"Prompt: {prompt}")
        if system_prompt:
            logger.debug(f"System Prompt: {system_prompt}")
    
    def log_response(self, response, elapsed_time):
        """
        Log the details of the API response
        
        Args:
            response (str): The response content
            elapsed_time (float): Time taken for the API call
        """
        logger.info(f"Received response from Grok API in {elapsed_time:.2f} seconds")
        logger.debug(f"Response: {response}")
    
    def call(self, prompt, **kwargs):
        """
        Call Grok API to generate a response
        
        Args:
            prompt (str): The prompt to send to the API
            **kwargs: Additional parameters including:
                system_prompt (str): Optional system prompt to set context
                model (str): The model to use (default: grok-3)
            
        Returns:
            str: The generated text response
        """
        start_time = time.time()
        try:
            if not self.api_key:
                return "Grok API key not found. Please set it in the .env file."
            
            # Create messages array with proper format
            messages = []
            
            # Add system prompt if provided
            system_prompt = kwargs.get("system_prompt")
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            # Add user message
            messages.append({"role": "user", "content": prompt})
            
            # Get model name from kwargs or use default
            model = kwargs.get("model", "grok-3")
            
            # Prepare data for API call
            data = {
                "model": model,
                "messages": messages,
                "stream": False
            }
            
            # Log the request details
            self.log_request(prompt, model, system_prompt)
            
            # Make the API call
            conn = http.client.HTTPSConnection(self.base_domain)
            conn.request("POST", self.endpoint, json.dumps(data), self.headers)
            response = conn.getresponse()
            response_data = json.loads(response.read().decode())
            conn.close()
            
            if response.status == 200:
                result = response_data["choices"][0]["message"]["content"]
                
                # Log the response
                elapsed_time = time.time() - start_time
                self.log_response(result, elapsed_time)
                
                return result
            else:
                error_message = f"Error from Grok API: {response.status} - {response_data}"
                logger.error(error_message)
                return error_message
                
        except Exception as e:
            elapsed_time = time.time() - start_time
            error_message = f"Exception calling Grok API: {str(e)}"
            logger.error(error_message)
            return error_message
    
    def call_stream(self, prompt, **kwargs):
        """
        Call Grok API with streaming support
        
        Args:
            prompt (str): The prompt to send to the API
            **kwargs: Additional parameters including:
                system_prompt (str): Optional system prompt to set context
                model (str): The model to use (default: grok-3)
            
        Returns:
            Generator: A generator that yields partial responses
        """
        start_time = time.time()
        try:
            if not self.api_key:
                yield "Grok API key not found. Please set it in the .env file."
                return
            
            # Create messages array with proper format
            messages = []
            
            # Add system prompt if provided
            system_prompt = kwargs.get("system_prompt")
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            # Add user message
            messages.append({"role": "user", "content": prompt})
            
            # Get model name from kwargs or use default
            model = kwargs.get("model", "grok-3")
            
            # Prepare data for API call
            data = {
                "model": model,
                "messages": messages,
                "stream": True
            }
            
            # Log the request details
            self.log_request(prompt, model, system_prompt)
            
            # Make the API call
            conn = http.client.HTTPSConnection(self.base_domain)
            conn.request("POST", self.endpoint, json.dumps(data), self.headers)
            response = conn.getresponse()
            
            if response.status == 200:
                full_response = ""
                while True:
                    chunk = response.read(1024)
                    if not chunk:
                        break
                    
                    # Process the chunk
                    chunk_str = chunk.decode('utf-8')
                    lines = chunk_str.split('\n')
                    
                    for line in lines:
                        if line.startswith('data: '):
                            if line.strip() == 'data: [DONE]':
                                continue
                            
                            json_str = line[6:].strip()
                            if not json_str:
                                continue
                            
                            try:
                                chunk_data = json.loads(json_str)
                                if 'choices' in chunk_data and len(chunk_data['choices']) > 0:
                                    delta = chunk_data['choices'][0].get('delta', {})
                                    if 'content' in delta and delta['content']:
                                        # Only yield the new content chunk, not the full response
                                        yield delta['content']
                                        full_response += delta['content']
                            except json.JSONDecodeError:
                                logger.warning(f"Failed to parse JSON from chunk: {json_str}")
                
                # Log the complete response at the end
                elapsed_time = time.time() - start_time
                self.log_response(full_response, elapsed_time)
                
            else:
                error_message = f"Error from Grok API: {response.status}"
                logger.error(error_message)
                yield error_message
                
            conn.close()
                
        except Exception as e:
            elapsed_time = time.time() - start_time
            error_message = f"Exception streaming from Grok API: {str(e)}"
            logger.error(error_message)
            yield error_message