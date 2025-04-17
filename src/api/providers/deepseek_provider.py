import os
import json
import requests
import logging
import time
from ..base_provider import LLMProvider
from openai import OpenAI

logger = logging.getLogger("llm_client")

class DeepSeekProvider(LLMProvider):
    """
    DeepSeek API provider implementation
    """
    def __init__(self, api_key=None):
        """
        Initialize DeepSeek provider
        
        Args:
            api_key (str, optional): DeepSeek API key
        """
        super().__init__(api_key)
        self.api_key = api_key or os.getenv('DEEPSEEK_API_KEY')
        self.base_url = "https://api.deepseek.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        # Create OpenAI client for Deepseek API
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        
        # Available DeepSeek models as per documentation
        # https://platform.deepseek.com/usage
        self.available_models = [
            "deepseek-chat", 
            "deepseek-coder", 
            "deepseek-coder-v2", 
            "deepseek-coder-instruct-v2", 
            "deepseek-llm-67b-chat", 
            "deepseek-math-7b-instruct",
            "deepseek-reasoner"  # Added deepseek-reasoner model
        ]
    
    def call(self, prompt, **kwargs):
        """
        Call DeepSeek API to generate a response
        
        Args:
            prompt (str): The prompt to send to the API
            **kwargs: Additional parameters including:
                system_prompt (str): Optional system prompt to set context
                model (str): The model to use (default: deepseek-chat)
            
        Returns:
            str: The generated text response
        """
        start_time = time.time()
        
        try:
            if not self.api_key:
                return "DeepSeek API key not found. Please set it in the .env file."
                
            # Create messages array with proper format
            messages = []
            
            # Add system prompt if provided
            system_prompt = kwargs.get("system_prompt", "You are a helpful assistant.")
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            # Add user message
            messages.append({"role": "user", "content": prompt})
            
            # Get model name from kwargs or use default
            model = kwargs.get("model", "deepseek-chat")
            
            # Validate model
            if model not in self.available_models:
                logger.warning(f"Model '{model}' not in DeepSeek API available models list. Falling back to deepseek-chat.")
                model = "deepseek-chat"
                
            temperature = kwargs.get("temperature", 0.7)
            max_tokens = kwargs.get("max_tokens", 2000)
            
            # Log the request using the base class method
            self.log_request("DeepSeek", prompt, model=model, system_prompt=system_prompt)
            
            # Using the OpenAI client with Deepseek API
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False
            )
            
            response_text = response.choices[0].message.content
            
            # Log the response using the base class method
            elapsed_time = time.time() - start_time
            self.log_response("DeepSeek", response_text, elapsed_time)
            
            return response_text
            
        except Exception as e:
            error_msg = f"Error calling DeepSeek API: {e}"
            logger.error(error_msg)
            # Log the error response
            self.log_response("DeepSeek", f"ERROR: {error_msg}", time.time() - start_time)
            # Include the DeepSeek platform URL for reference
            return f"{error_msg}\nPlease verify your API key and model at https://platform.deepseek.com/usage"
    
    def call_stream(self, prompt, **kwargs):
        """
        Call DeepSeek API with streaming support
        
        Args:
            prompt (str): The prompt to send to the API
            **kwargs: Additional parameters including:
                system_prompt (str): Optional system prompt to set context
                model (str): The model to use (default: deepseek-chat)
            
        Yields:
            str: Response chunks (only new content)
        """
        start_time = time.time()
        full_response = ""
        
        try:
            if not self.api_key:
                yield "DeepSeek API key not found. Please set it in the .env file."
                return
                
            # Create messages array with proper format
            messages = []
            
            # Add system prompt if provided
            system_prompt = kwargs.get("system_prompt", "You are a helpful assistant.")
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            # Add user message
            messages.append({"role": "user", "content": prompt})
            
            # Get model name and parameters from kwargs or use defaults
            model = kwargs.get("model", "deepseek-chat")
            
            # Validate model
            if model not in self.available_models:
                logger.warning(f"Model '{model}' not in DeepSeek API available models list. Falling back to deepseek-chat.")
                model = "deepseek-chat"
                
            temperature = kwargs.get("temperature", 0.7)
            max_tokens = kwargs.get("max_tokens", 2000)
            
            # Log the request using the base class method
            self.log_request("DeepSeek", prompt, model=model, system_prompt=system_prompt)
            
            # Using the OpenAI client with streaming
            stream = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            
            # Process the streaming response, yielding only new content each time
            for chunk in stream:
                if hasattr(chunk.choices[0].delta, "content") and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    yield content
            
            # Log the complete response at the end of streaming
            elapsed_time = time.time() - start_time
            self.log_response("DeepSeek", full_response, elapsed_time)
                    
        except Exception as e:
            error_msg = f"Error in DeepSeek streaming: {e}"
            logger.error(error_msg)
            # Log the error response
            self.log_response("DeepSeek", f"ERROR: {error_msg}", time.time() - start_time)
            # Include the DeepSeek platform URL for reference
            yield f"{error_msg}\nPlease verify your API key and model at https://platform.deepseek.com/usage"