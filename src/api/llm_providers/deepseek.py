import requests
import json
import logging
from ..llm_client import LLMProvider

logger = logging.getLogger("deepseek_provider")

class DeepseekProvider(LLMProvider):
    """
    Implementation of DeepSeek API provider
    """
    def __init__(self, api_key=None):
        """
        Initialize DeepSeek provider
        
        Args:
            api_key (str, optional): DeepSeek API key
        """
        super().__init__(api_key)
        if not self.api_key:
            logger.warning("DeepSeek API key is not provided")
    
    def call(self, prompt, **kwargs):
        """
        Call DeepSeek API to generate response
        
        Args:
            prompt (str): Prompt text
            **kwargs: Additional parameters, including:
                model (str): Model to use (default: deepseek-chat)
                max_tokens (int): Maximum tokens in response (default: 1000)
                temperature (float): Temperature for response generation (default: 0.7)
                system_prompt (str): System prompt defining AI's role and behavior
                
        Returns:
            str: Generated text response
        """
        model = kwargs.get('model', 'deepseek-chat')
        max_tokens = kwargs.get('max_tokens', 1000)
        temperature = kwargs.get('temperature', 0.7)
        system_prompt = kwargs.get('system_prompt')
        
        if not self.api_key:
            return "DeepSeek API key not found. Please set it in the .env file."
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # Create messages array with proper format
        messages = []
        
        # Add system prompt if provided
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Add user message
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": model,
            "messages": messages,
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
            logger.error(f"Error calling DeepSeek API: {e}")
            return f"Error calling DeepSeek API: {str(e)}"
    
    def call_stream(self, prompt, **kwargs):
        """
        Call DeepSeek API with streaming support to generate response
        
        Args:
            prompt (str): Prompt to send to API
            **kwargs: Additional parameters, including:
                model (str): Base model name to use (default: deepseek-chat)
                max_tokens (int): Maximum tokens in response (default: 1000)
                temperature (float): Temperature for response generation (default: 0.7)
                mode (str): Whether to use 'chat' or 'reasoner' mode (default: chat)
                system_prompt (str): System prompt defining AI's role and behavior
                
        Returns:
            Generator: Yields chunks of generated text response, with complete response at the end
        """
        model = kwargs.get('model', '')
        max_tokens = kwargs.get('max_tokens', 1000)
        temperature = kwargs.get('temperature', 0.7)
        mode = kwargs.get('mode', 'chat')
        system_prompt = kwargs.get('system_prompt')
        
        if not self.api_key:
            yield "DeepSeek API key not found. Please set it in the .env file."
            return
        
        # Adjust model name based on mode
        if mode == "reasoner" or model == "deepseek-reasoner":
            # If user specifically requests the reasoner model or mode
            model = "deepseek-reasoner"
        elif not model:
            # Default model if none specified
            model = "deepseek-chat"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # Create messages array with proper format
        messages = []
        
        # Add system prompt if provided (prioritize explicit system_prompt over mode)
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        elif mode == "reasoner":
            messages.append({
                "role": "system", 
                "content": "You are a helpful AI assistant with reasoning capabilities. Think through problems step by step."
            })
            model = "deepseek-reasoner"
        
        # Add user message
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
            logger.info(f"Making request to DeepSeek API with model: {model}")
            
            # Stream the response
            response = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers=headers,
                json=payload,
                stream=True
            )
            
            # Check for errors
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
                    # Skip "data: " prefix
                    line = line.decode('utf-8')
                    if line.startswith("data: "):
                        line = line[6:]  # Skip "data: "
                    
                    # Check for [DONE] message
                    if line == "[DONE]":
                        # Ensure final complete response is yielded
                        if final_content:
                            yield final_content
                        break
                    
                    try:
                        json_response = json.loads(line)
                        # Extract content - may vary based on actual DeepSeek API response format
                        if "choices" in json_response and json_response["choices"]:
                            delta = json_response["choices"][0].get("delta", {})
                            if "content" in delta and delta["content"]:
                                collected_content += delta["content"]
                                # Track complete response for final yield
                                final_content = collected_content
                                yield collected_content
                    except json.JSONDecodeError:
                        # Skip lines that can't be decoded as JSON
                        pass
                        
            # Ensure final response is yielded again after stream completes
            # This helps prevent incomplete response errors
            if final_content:
                yield final_content
                
        except Exception as e:
            logger.error(f"Error streaming from DeepSeek API: {e}")
            yield f"Error streaming from DeepSeek API: {str(e)}"