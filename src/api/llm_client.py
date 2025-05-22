import os
import time
import logging

from core.config import config
from .base_provider import LLMProvider

# Fixed imports: Import from the correct location
try:
    # First try llm_providers which has the chatapi.littlewheat.com endpoint
    from .llm_providers import GrokProvider, DeepSeekProvider, OpenAIProvider
    logger = logging.getLogger("llm_client")
    logger.info("Loaded providers from api.llm_providers package")
except ImportError as e:
    # Fall back to providers if that fails
    try:
        from .providers import GrokProvider, DeepSeekProvider, OpenAIProvider
        logger = logging.getLogger("llm_client")
        logger.info("Loaded providers from api.providers package")
    except ImportError:
        # If both fail, log an error
        logger = logging.getLogger("llm_client")
        logger.error(f"Failed to import LLM providers: {e}")
        # Use stub providers as fallback
        class StubProvider(LLMProvider):
            def call(self, prompt, **kwargs):
                return f"Provider not available. Error importing providers."
            def call_stream(self, prompt, **kwargs):
                yield f"Provider not available. Error importing providers."
        
        GrokProvider = DeepSeekProvider = OpenAIProvider = StubProvider

class LLMClient:
    """
    Unified LLM client for interacting with various LLM providers
    """
    def __init__(self):
        """
        Initialize the LLM client, loading API keys and providers
        """
        self.environment = config.environment
        self.providers = {}
        
        # Store API keys for direct access if needed
        self.grok_api_key = os.getenv('GROK_API_KEY')
        self.deepseek_api_key = os.getenv('DEEPSEEK_API_KEY')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.github_api_key = os.getenv('GITHUB_API_KEY')
        
        # Register all providers
        self._register_providers()
    
    def _register_providers(self):
        """
        Register all available LLM providers
        """
        # Register Grok provider
        grok_api_key = self.grok_api_key
        if grok_api_key:
            self.register_provider('grok', GrokProvider(grok_api_key))
            logger.info("Grok provider registered")
        
        # Register DeepSeek provider
        deepseek_api_key = self.deepseek_api_key
        if deepseek_api_key:
            self.register_provider('deepseek', DeepSeekProvider(deepseek_api_key))
            logger.info("DeepSeek provider registered")
        
        # Register OpenAI provider (using GitHub API key)
        github_api_key = self.github_api_key
        if github_api_key:
            self.register_provider('openai', OpenAIProvider(github_api_key))
            logger.info("OpenAI provider registered (using GitHub API)")
    
    def register_provider(self, provider_name, provider_instance):
        """
        Register an LLM provider
        
        Args:
            provider_name (str): The name of the provider
            provider_instance (LLMProvider): The provider instance
        """
        self.providers[provider_name] = provider_instance
        logger.info(f"Registered LLM provider: {provider_name}")
    
    def call_llm(self, provider, prompt, **kwargs):
        """
        Route LLM calls based on environment settings
        
        Args:
            provider (str): The API provider to use ('openai', 'deepseek', 'github', 'grok', etc.)
            prompt (str): The prompt to send to the API
            **kwargs: Additional parameters to pass to the specific API call
            
        Returns:
            str: The generated text response from the API or the test response
        """
        # In test environment, use the test API regardless of provider
        if config.is_test_environment():
            logger.info(f"Environment is set to test, routing {provider} call to test API")
            return self._call_test(prompt, **kwargs)
        
        # Check if the provider is registered
        if provider not in self.providers:
            # Special handling for 'github' provider - redirect to 'openai' provider
            if provider == 'github' and 'openai' in self.providers:
                logger.info(f"Redirecting 'github' provider call to 'openai' provider")
                provider = 'openai'
            else:
                return f"Unknown provider: {provider}"
        
        # Handle system_prompt if provided
        system_prompt = kwargs.get('system_prompt', '')
        
        # Format the system prompt for better display if needed
        enhanced_system_prompt = system_prompt
        if system_prompt and not "Format your response" in system_prompt:
            enhanced_system_prompt = system_prompt + " Format your response clearly with proper spacing, line breaks, and structure. Use markdown-style formatting like *bold*, _italic_, and `code` for emphasis. Use numbered lists (1., 2., 3.) and bullet points (- or *) for lists. Ensure your response is well-structured and easy to read."
        elif not system_prompt:
            enhanced_system_prompt = "You are a helpful AI assistant. Format your response clearly with proper spacing, line breaks, and structure. Use markdown-style formatting like *bold*, _italic_, and `code` for emphasis. Use numbered lists (1., 2., 3.) and bullet points (- or *) for lists. Ensure your response is well-structured and easy to read."
        
        # Update kwargs with enhanced system prompt
        kwargs['system_prompt'] = enhanced_system_prompt
        
        logger.info(f"Calling {provider} with prompt: {prompt}")
        response = self.providers[provider].call(prompt, **kwargs)
        self.logger.info(f"Response from {provider}: {response[:100]}...")  # Log first 100 chars
        return response
    
    def call_llm_stream(self, provider, prompt, **kwargs):
        """
        Call LLM with streaming support
        
        Args:
            provider (str): The provider to use
            prompt (str): The prompt
            **kwargs: Additional parameters
            
        Returns:
            Generator: A generator yielding text response chunks
        """
        # Use test response in test environment
        if config.is_test_environment():
            logger.info(f"Environment is set to test, routing {provider} streaming call to test API")
            yield from self._call_test_stream(prompt, **kwargs)
            return
        
        # Check if the provider is registered
        if provider not in self.providers:
            # Special handling for 'github' provider - redirect to 'openai' provider
            yield f"Unknown provider: {provider}"
            return
        
        # Handle system_prompt if provided
        system_prompt = kwargs.get('system_prompt', '')
        
        # Format the system prompt for better display if needed
        enhanced_system_prompt = system_prompt
        if system_prompt and not "Format your response" in system_prompt:
            enhanced_system_prompt = system_prompt + " Format your response clearly with proper spacing, line breaks, and structure. Use markdown-style formatting like *bold*, _italic_, and `code` for emphasis. Use numbered lists (1., 2., 3.) and bullet points (- or *) for lists. Ensure your response is well-structured and easy to read."
        elif not system_prompt:
            enhanced_system_prompt = "You are a helpful AI assistant. Format your response clearly with proper spacing, line breaks, and structure. Use markdown-style formatting like *bold*, _italic_, and `code` for emphasis. Use numbered lists (1., 2., 3.) and bullet points (- or *) for lists. Ensure your response is well-structured and easy to read."
        
        # Update kwargs with enhanced system prompt
        kwargs['system_prompt'] = enhanced_system_prompt
        
        # Call the provider's streaming implementation
        logger.info(f"Starting streaming call to {provider} with prompt: {prompt}")
        yield from self.providers[provider].call_stream(prompt, **kwargs)
    
    def _call_test(self, prompt=None, delay=2):
        """
        Test interface that simulates an API call by waiting and returning a fixed response
        
        Args:
            prompt (str): The prompt (unused in this test interface, included for API consistency)
            delay (int): Seconds to wait before responding (default: 2)
            
        Returns:
            str: A fixed "Hello world" response after the delay
        """
        # Log that a test call is being made
        logger.info(f"Test API called with prompt: {prompt}")
        
        # Simulate API processing time
        time.sleep(delay)
        
        # Return a fixed test response
        return "Hello World\nService is currently unavailable. This is a test response."
    
    def _call_test_stream(self, prompt=None, delay=2, chunks=5):
        """
        Test interface that simulates a streaming API call
        
        Args:
            prompt (str): The prompt (unused in this test interface, included for API consistency)
            delay (int): Total response time in seconds (default: 2)
            chunks (int): Number of chunks to return (default: 5)
            
        Yields:
            str: Response chunks
        """
        # Log that a test streaming call is being made
        logger.info(f"Test streaming API called with prompt: {prompt}")
        
        # Calculate delay between chunks
        chunk_delay = delay / chunks
        
        # Base response
        base_response = "Hello World\nService is currently unavailable. This is a test response."
        
        # Generate chunks
        for i in range(chunks):
            # For each chunk, return an increasing portion
            progress = (i + 1) / chunks
            response_part = base_response[:int(len(base_response) * progress)]
            
            # Sleep to simulate streaming
            time.sleep(chunk_delay)
            
            # Yield partial response
            yield response_part