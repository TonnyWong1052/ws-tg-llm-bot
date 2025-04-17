from abc import ABC, abstractmethod
import logging
import time

logger = logging.getLogger("llm_provider")

class LLMProvider(ABC):
    """
    Abstract base class for LLM providers, all provider implementations should inherit from this class
    """
    def __init__(self, api_key=None):
        """
        Initialize the LLM provider
        
        Args:
            api_key (str, optional): API key
        """
        self.api_key = api_key
    
    def log_request(self, provider_name, prompt, **kwargs):
        """
        Log the LLM API request
        
        Args:
            provider_name (str): Name of the provider
            prompt (str): The prompt sent to the API
            **kwargs: Additional request parameters
        """
        # Truncate prompt if too long for logging
        log_prompt = prompt if len(prompt) < 500 else prompt[:500] + "... [truncated]"
        
        # Log model name if available
        model_info = f", model: {kwargs.get('model')}" if kwargs.get('model') else ""
        
        # Log request with timestamp
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"[{timestamp}] API REQUEST to {provider_name}{model_info}:")
        logger.info(f"Prompt: {log_prompt}")
        
        # Log other important parameters
        system_prompt = kwargs.get('system_prompt')
        if system_prompt:
            log_system_prompt = system_prompt if len(system_prompt) < 200 else system_prompt[:200] + "... [truncated]"
            logger.info(f"System prompt: {log_system_prompt}")
    
    def log_response(self, provider_name, response, elapsed_time=None):
        """
        Log the LLM API response
        
        Args:
            provider_name (str): Name of the provider
            response (str): The response from the API
            elapsed_time (float, optional): Time taken for the request in seconds
        """
        # Truncate response if too long for logging
        log_response = response if len(response) < 500 else response[:500] + "... [truncated]"
        
        # Log response with timestamp
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        time_info = f" (took {elapsed_time:.2f}s)" if elapsed_time is not None else ""
        
        logger.info(f"[{timestamp}] API RESPONSE from {provider_name}{time_info}:")
        logger.info(f"Response: {log_response}")
    
    @abstractmethod
    def call(self, prompt, **kwargs):
        """
        Call the LLM API to generate a response
        
        Args:
            prompt (str): The prompt to send to the API
            **kwargs: Additional provider-specific parameters
            
        Returns:
            str: The generated text response
        """
        pass
    
    @abstractmethod
    def call_stream(self, prompt, **kwargs):
        """
        Call the LLM API to generate a response with streaming support
        
        Args:
            prompt (str): The prompt to send to the API
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Generator: Chunks of the generated text response
        """
        pass