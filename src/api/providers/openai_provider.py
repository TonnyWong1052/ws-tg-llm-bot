import os
import json
import requests
import logging
from openai import OpenAI
from ..base_provider import LLMProvider

logger = logging.getLogger("llm_client")

class OpenAIProvider(LLMProvider):
    """
    OpenAI API provider implementation that uses GitHub API endpoint
    """
    def __init__(self, api_key=None):
        """
        Initialize OpenAI provider
        
        Args:
            api_key (str, optional): GitHub API key for calling OpenAI models
        """
        super().__init__(api_key)
        self.api_key = api_key or os.getenv('GITHUB_API_KEY')  # Use GitHub API key
        self.endpoint = "https://models.inference.ai.azure.com"  # GitHub API endpoint
    
    def call(self, prompt, **kwargs):
        """
        Call OpenAI API via GitHub API to generate a response
        
        Args:
            prompt (str): The prompt to send to the API
            **kwargs: Additional parameters including:
                system_prompt (str): Optional system prompt to set context
                model (str): The model to use (default: gpt-4o-mini)
            
        Returns:
            str: The generated text response
        """
        try:
            if not self.api_key:
                return "GitHub API key not found. Please set it in the .env file."
                
            # Get parameters from kwargs
            system_prompt = kwargs.get("system_prompt", "You are a helpful assistant.")
            model = kwargs.get("model", "gpt-4o-mini")
            temperature = kwargs.get("temperature", 0.7)
            max_tokens = kwargs.get("max_tokens", 2000)
            
            # Log the request
            self.log_request("OpenAI", prompt, model=model, system_prompt=system_prompt)
            
            # Create OpenAI client with GitHub API endpoint
            client = OpenAI(
                base_url=self.endpoint,
                api_key=self.api_key,
            )

            # Record start time for timing
            import time
            start_time = time.time()

            # Make the API call
            response = client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                temperature=temperature,
                top_p=1.0,
                max_tokens=max_tokens,
                model=model
            )
            
            response_content = response.choices[0].message.content
            
            # Log the response
            elapsed_time = time.time() - start_time
            self.log_response("OpenAI", response_content, elapsed_time)
            
            return response_content
            
        except Exception as e:
            logger.error(f"Error calling OpenAI API via GitHub: {e}")
            return f"Error calling OpenAI API: {str(e)}"
    
    def call_stream(self, prompt, **kwargs):
        """
        Call OpenAI API via GitHub API with streaming support
        
        Args:
            prompt (str): The prompt to send to the API
            **kwargs: Additional parameters including:
                system_prompt (str): Optional system prompt to set context
                model (str): The model to use (default: gpt-4o-mini)
            
        Yields:
            str: Response chunks
        """
        try:
            if not self.api_key:
                yield "GitHub API key not found. Please set it in the .env file."
                return
                
            # Get parameters from kwargs
            system_prompt = kwargs.get("system_prompt", "You are a helpful assistant.")
            model = kwargs.get("model", "gpt-4o-mini")
            temperature = kwargs.get("temperature", 0.7)
            max_tokens = kwargs.get("max_tokens", 2000)
            
            # Log the request
            self.log_request("OpenAI (Stream)", prompt, model=model, system_prompt=system_prompt)
            
            # Record start time for timing
            import time
            start_time = time.time()
            
            # Create OpenAI client with GitHub API endpoint
            client = OpenAI(
                base_url=self.endpoint,
                api_key=self.api_key,
            )

            # Make the streaming API call
            stream = client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                temperature=temperature,
                top_p=1.0,
                max_tokens=max_tokens,
                model=model,
                stream=True
            )
            
            collected_content = ""
            
            # Process the streaming response
            for chunk in stream:
                if hasattr(chunk, 'choices') and len(chunk.choices) > 0 and hasattr(chunk.choices[0], 'delta'):
                    delta = chunk.choices[0].delta
                    if hasattr(delta, "content") and delta.content:
                        content = delta.content
                        collected_content += content
                        yield content
            
            # If no content was collected, yield a placeholder message
            if not collected_content:
                yield "No response content received from the model."
            
            # Log the final complete response
            elapsed_time = time.time() - start_time
            self.log_response("OpenAI (Stream)", collected_content, elapsed_time)
                    
        except Exception as e:
            logger.error(f"Error in streaming OpenAI API via GitHub: {e}")
            yield f"Error in OpenAI streaming: {str(e)}"
            # Add a fallback response so the user gets something useful
            yield "\n\nFallback message: I'm having trouble connecting to the OpenAI service. Please check your API key and network connection, then try again."