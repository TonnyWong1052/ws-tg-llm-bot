import requests
import json
import logging
from ..llm_client import LLMProvider

logger = logging.getLogger("deepseek_provider")

class DeepseekProvider(LLMProvider):
    """
    DeepSeek API 的提供商實現
    """
    def __init__(self, api_key=None):
        """
        初始化 DeepSeek 提供商
        
        Args:
            api_key (str, optional): DeepSeek API 密鑰
        """
        super().__init__(api_key)
        if not self.api_key:
            logger.warning("DeepSeek API key is not provided")
    
    def call(self, prompt, **kwargs):
        """
        調用 DeepSeek API 生成響應
        
        Args:
            prompt (str): 提示
            **kwargs: 附加參數，包括:
                model (str): 要使用的模型 (默認: deepseek-chat)
                max_tokens (int): 響應中的最大標記數 (默認: 1000)
                temperature (float): 響應生成的溫度 (默認: 0.7)
                system_prompt (str): 系統提示，定義 AI 的角色和行為
                
        Returns:
            str: 生成的文本響應
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
        使用流式支持調用 DeepSeek API 生成響應
        
        Args:
            prompt (str): 要發送到 API 的提示
            **kwargs: 附加參數，包括:
                model (str): 要使用的模型基礎名稱 (默認: deepseek-chat)
                max_tokens (int): 響應中的最大標記數 (默認: 1000)
                temperature (float): 響應生成的溫度 (默認: 0.7)
                mode (str): 是使用 'chat' 還是 'reasoner' 模式 (默認: chat)
                system_prompt (str): 系統提示，定義 AI 的角色和行為
                
        Returns:
            Generator: 生成文本響應的塊，最終完整響應在末尾
        """
        model = kwargs.get('model', '')
        max_tokens = kwargs.get('max_tokens', 1000)
        temperature = kwargs.get('temperature', 0.7)
        mode = kwargs.get('mode', 'chat')
        system_prompt = kwargs.get('system_prompt')
        
        if not self.api_key:
            yield "DeepSeek API key not found. Please set it in the .env file."
            return
        
        # 根據模式調整模型名稱
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
        
        # 添加用戶消息
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True
        }
        
        try:
            # 打印請求詳細信息以進行調試
            logger.info(f"Making request to DeepSeek API with model: {model}")
            
            # 流式處理響應
            response = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers=headers,
                json=payload,
                stream=True
            )
            
            # 檢查錯誤
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
                    # 跳過 "data: " 前綴
                    line = line.decode('utf-8')
                    if line.startswith("data: "):
                        line = line[6:]  # 跳過 "data: "
                    
                    # 檢查 [DONE] 消息
                    if line == "[DONE]":
                        # 確保最後一次生成完整的響應
                        if final_content:
                            yield final_content
                        break
                    
                    try:
                        json_response = json.loads(line)
                        # 提取內容 - 可能根據實際的 DeepSeek API 響應格式而有所不同
                        if "choices" in json_response and json_response["choices"]:
                            delta = json_response["choices"][0].get("delta", {})
                            if "content" in delta and delta["content"]:
                                collected_content += delta["content"]
                                # 跟踪完整響應以便最後生成
                                final_content = collected_content
                                yield collected_content
                    except json.JSONDecodeError:
                        # 跳過無法解碼為 JSON 的行
                        pass
                        
            # 確保在流完成後再次生成最終響應
            # 這有助於防止響應不完整的錯誤
            if final_content:
                yield final_content
                
        except Exception as e:
            logger.error(f"Error streaming from DeepSeek API: {e}")
            yield f"Error streaming from DeepSeek API: {str(e)}"