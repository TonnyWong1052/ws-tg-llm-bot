import os
import sys
from dotenv import load_dotenv
import toml

# Add parent directory to Python path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Load environment variables
config_path = os.path.join(os.path.dirname(parent_dir), 'config', '.env')
load_dotenv(config_path)

class Config:
    """
    Application configuration management class
    """
    def __init__(self):
        # Load basic configuration from environment variables
        self.api_id = int(os.getenv('API_ID', 0))
        self.api_hash = os.getenv('API_HASH', '')
        self.phone_number = os.getenv('PHONE_NUMBER', '')
        self.environment = os.getenv('ENVIRONMENT', 'test')
        
        # Load API keys
        self.openai_api_key = os.getenv('OPENAI_API_KEY', '')
        self.deepseek_api_key = os.getenv('DEEPSEEK_API_KEY', '')
        self.github_api_key = os.getenv('GITHUB_API_KEY', '')
        self.grok_api_key = os.getenv('GROK_API_KEY', '')
        
        # Load from credentials file (as fallback)
        self._load_credentials()
        
        # Message length limits
        self.telegram_max_length = 2500
        
        # Retry settings
        self.max_retries = 3
        self.retry_delay = 2
        
    def _load_credentials(self):
        """
        Load configuration from credentials file (if exists)
        """
        config_dir = os.path.join(os.path.dirname(parent_dir), 'config')
        file_path = os.path.join(config_dir, 'credentials') if os.path.exists(config_dir) else 'credentials'
        
        if os.path.exists(file_path):
            try:
                self.secrets = toml.load(file_path)
                
                # Load from credentials file if not in environment variables
                if not self.openai_api_key and 'openai' in self.secrets:
                    self.openai_api_key = self.secrets.get('openai', {}).get('api_key', '')
                    
                if not self.deepseek_api_key and 'deepseek' in self.secrets:
                    self.deepseek_api_key = self.secrets.get('deepseek', {}).get('api_key', '')
                    
                if not self.github_api_key and 'github' in self.secrets:
                    self.github_api_key = self.secrets.get('github', {}).get('api_key', '')
                    
                if not self.grok_api_key and 'grok' in self.secrets:
                    self.grok_api_key = self.secrets.get('grok', {}).get('api_key', '')
            except Exception as e:
                print(f"Error loading credentials file: {e}")
                self.secrets = {}
        else:
            self.secrets = {}
    
    def is_test_environment(self):
        """
        Check if running in test environment
        """
        return self.environment.lower() == 'test'
    
    def get_api_key(self, provider):
        """
        Get API key for specified provider
        """
        if provider == 'openai':
            return self.openai_api_key
        elif provider == 'deepseek':
            return self.deepseek_api_key
        elif provider == 'github':
            return self.github_api_key
        elif provider == 'grok':
            return self.grok_api_key
        else:
            return None

# Global config instance
config = Config() 