import requests
import json
import logging
from ..llm_client import LLMProvider

logger = logging.getLogger("openai_provider")

class OpenAIProvider(LLMProvider):
    """
    OpenAI API 的提供商實現
    """
    def __init__(self, api_key=None):
        """
        初始化 OpenAI 提供商
        
        Args:
            api_key (str, optional): OpenAI API 密鑰
        """
        super().__init__(api_key)
        if not self.api_key:
            logger.warning("OpenAI API key is not provided")
    
    def call(self, prompt, **kwargs):
        """
        調用 OpenAI API 生成響應
        
        Args:
            prompt (str): 提示
            **kwargs: 附加參數，包括:
                model (str): 要使用的模型 (默認: gpt-3.5-turbo)
                max_tokens (int): 響應中的最大標記 (默認: 1000)
                
        Returns:
            str: 生成的文本響應
        """
        model = kwargs.get('model', 'gpt-3.5-turbo')
        max_tokens = kwargs.get('max_tokens', 1000)
        
        if not self.api_key:
            return "OpenAI API key not found. Please set it in the .env file."
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
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
            logger.error(f"Error calling OpenAI API: {e}")
            return f"Error calling OpenAI API: {str(e)}"
    
    def call_stream(self, prompt, **kwargs):
        """
        使用流式支持調用 OpenAI API 生成響應
        
        Args:
            prompt (str): 提示
            **kwargs: 附加參數，包括:
                model (str): 要使用的模型 (默認: gpt-3.5-turbo)
                max_tokens (int): 最大標記數 (默認: 1000)
                system_prompt (str): 系統提示 (默認: None)
                
        Returns:
            Generator: 生成部分響應的生成器
        """
        model = kwargs.get('model', 'gpt-3.5-turbo')
        max_tokens = kwargs.get('max_tokens', 1000)
        system_prompt = kwargs.get('system_prompt', None)
        
        if not self.api_key:
            yield "OpenAI API key not found. Please set it in the .env file."
            return
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # 準備消息
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": True
        }
        
        try:
            # 流式處理響應
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                stream=True
            )
            response.raise_for_status()
            
            collected_content = ""
            for line in response.iter_lines():
                if line:
                    # 跳過保持活動行
                    line = line.decode('utf-8')
                    if line.startswith("data: "):
                        if line == "data: [DONE]":
                            break
                        
                        data = line[6:]  # 去掉 "data: " 前綴
                        try:
                            json_data = json.loads(data)
                            # 從增量更新中提取內容
                            delta = json_data.get("choices", [{}])[0].get("delta", {})
                            if "content" in delta:
                                content_chunk = delta["content"]
                                collected_content += content_chunk
                                yield collected_content
                        except json.JSONDecodeError:
                            pass
                            
            # 確保最後生成完整響應
            if collected_content:
                yield collected_content
                
        except Exception as e:
            logger.error(f"Error streaming from OpenAI API: {e}")
            yield f"Error streaming from OpenAI API: {str(e)}" 