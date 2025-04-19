import logging
from openai import OpenAI
from ..llm_client import LLMProvider

logger = logging.getLogger("github_provider")

class GitHubProvider(LLMProvider):
    """
    Implementation of GitHub (via Azure) API provider
    """
    def __init__(self, api_key=None):
        """
        Initialize GitHub provider
        
        Args:
            api_key (str, optional): GitHub API key
        """
        super().__init__(api_key)
        self.endpoint = "https://models.inference.ai.azure.com"
        if not self.api_key:
            logger.warning("GitHub API key is not provided")
    
    def call(self, prompt, **kwargs):
        """
        Call GitHub API to generate a response
        
        Args:
            prompt (str): User prompt
            **kwargs: Additional parameters, including:
                system_prompt (str): System prompt to set the context
                model_name (str): Model to use (default: gpt-4o-mini)
                
        Returns:
            str: Generated text response
        """
        system_prompt = kwargs.get('system_prompt', 'You are a helpful AI assistant.')
        model_name = kwargs.get('model_name', 'gpt-4o-mini')
        
        if not self.api_key:
            return "GitHub API key not found. Please set it in the .env file or credentials file."
        
        try:
            client = OpenAI(
                base_url=self.endpoint,
                api_key=self.api_key,
            )

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
                temperature=1.0,
                top_p=1.0,
                max_tokens=1000,
                model=model_name
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error calling GitHub API: {e}")
            return f"Error calling GitHub API: {str(e)}"
    
    def call_stream(self, prompt, **kwargs):
        """
        Call GitHub API with streaming support to generate a response
        
        Args:
            prompt (str): User prompt
            **kwargs: Additional parameters, including:
                system_prompt (str): System prompt to set the context
                model_name (str): Model to use (default: gpt-4o-mini)
                
        Returns:
            Generator: Generator of partial responses
        """
        system_prompt = kwargs.get('system_prompt', 'You are a helpful AI assistant.')
        model_name = kwargs.get('model_name', 'gpt-4o-mini')
        
        if not self.api_key:
            yield "GitHub API key not found. Please set it in the .env file or credentials file."
            return
        
        try:
            client = OpenAI(
                base_url=self.endpoint,
                api_key=self.api_key,
            )

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
                temperature=1.0,
                top_p=1.0,
                max_tokens=1000,
                model=model_name,
                stream=True
            )
            
            full_response = ""
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    yield full_response
                    
        except Exception as e:
            logger.error(f"Error streaming from GitHub API: {e}")
            yield f"Error streaming from GitHub API: {str(e)}"