import http.client
import json
import time
import logging
from ..llm_client import LLMProvider

logger = logging.getLogger("grok_provider")

class GrokProvider(LLMProvider):
    """
    Grok API 的提供商實現
    """
    def __init__(self, api_key=None):
        """
        初始化 Grok 提供商
        
        Args:
            api_key (str, optional): Grok API 密鑰
        """
        super().__init__(api_key)
        if not self.api_key:
            logger.warning("Grok API key is not provided")
    
    def call(self, prompt, **kwargs):
        """
        調用 Grok API 生成響應
        
        Args:
            prompt (str): 用戶提示
            **kwargs: 附加參數，包括:
                system_prompt (str): 設置上下文的系統提示
                model_name (str): 要使用的模型 (默認: grok-3)
                
        Returns:
            str: 生成的文本響應
        """
        system_prompt = kwargs.get('system_prompt', '')
        model_name = kwargs.get('model_name', 'grok-3')
        
        if not self.api_key:
            return "Grok API key not found. Please set GROK_API_KEY in the .env file or credentials file."
        
        # 改進系統提示以使用 Telegram 友好的格式
        enhanced_system_prompt = system_prompt
        if system_prompt and "Format your response" not in system_prompt:
            enhanced_system_prompt = system_prompt + " Format your response clearly with proper spacing, line breaks, and structure. Use markdown-style formatting like *bold*, _italic_, and `code` for emphasis. Use numbered lists (1., 2., 3.) and bullet points (- or *) for lists. Ensure your response is well-structured and easy to read."
        elif not system_prompt:
            enhanced_system_prompt = "You are a helpful AI assistant. Format your response clearly with proper spacing, line breaks, and structure. Use markdown-style formatting like *bold*, _italic_, and `code` for emphasis. Use numbered lists (1., 2., 3.) and bullet points (- or *) for lists. Ensure your response is well-structured and easy to read."
        
        try:
            # 設置與 API 端點的 HTTP 連接
            conn = http.client.HTTPSConnection("chatapi.littlewheat.com")
            
            # 設置消息
            messages = []
            if enhanced_system_prompt:
                messages.append({
                    "role": "system",
                    "content": enhanced_system_prompt
                })
            
            # 添加用戶消息
            messages.append({
                "role": "user", 
                "content": prompt
            })
            
            # 準備請求有效載荷
            payload = json.dumps({
                "model": model_name,
                "messages": messages,
                "stream": False,
                "temperature": 0.7,
                "max_tokens": 1000
            })
            
            # 設置帶有授權的標頭
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            # 發送請求
            conn.request("POST", "/v1/chat/completions", payload, headers)
            
            # 獲取響應
            res = conn.getresponse()
            data = res.read()
            
            # 解析響應
            if res.status != 200:
                return f"Error calling Grok API: HTTP status {res.status} - {data.decode('utf-8')}"
                
            response_data = json.loads(data.decode("utf-8"))
            return response_data["choices"][0]["message"]["content"]
            
        except Exception as e:
            logger.error(f"Error calling Grok API: {e}")
            return f"Error calling Grok API: {str(e)}"
    
    def call_stream(self, prompt, **kwargs):
        """
        使用流式支持調用 Grok API 生成響應
        
        Args:
            prompt (str): 用戶提示
            **kwargs: 附加參數，包括:
                system_prompt (str): 設置上下文的系統提示
                model_name (str): 要使用的模型 (默認: grok-3-reasoner)
                
        Returns:
            Generator: 生成部分響應的生成器
        """
        # 獲取關鍵字參數
        system_prompt = kwargs.get('system_prompt', '')
        model_name = kwargs.get('model_name', 'grok-3-reasoner')
        
        if not self.api_key:
            yield "Grok API key not found. Please set GROK_API_KEY in the .env file or credentials file."
            return
        
        # 改進系統提示
        enhanced_system_prompt = system_prompt
        if system_prompt and "Format your response" not in system_prompt:
            enhanced_system_prompt = system_prompt + " Format your response clearly with proper spacing, line breaks, and structure. Use markdown-style formatting like *bold*, _italic_, and `code` for emphasis. Use numbered lists (1., 2., 3.) and bullet points (- or *) for lists. Ensure your response is well-structured and easy to read."
        elif not system_prompt:
            enhanced_system_prompt = "You are a helpful AI assistant. Format your response clearly with proper spacing, line breaks, and structure. Use markdown-style formatting like *bold*, _italic_, and `code` for emphasis. Use numbered lists (1., 2., 3.) and bullet points (- or *) for lists. Ensure your response is well-structured and easy to read."
        
        # 設置消息
        messages = []
        if enhanced_system_prompt:
            messages.append({
                "role": "system",
                "content": enhanced_system_prompt
            })
        
        # 添加用戶消息
        messages.append({
            "role": "user", 
            "content": prompt
        })
        
        # 最大重試次數
        max_retries = 3
        retry_count = 0
        retry_delay = 2  # 秒
        
        while retry_count < max_retries:
            try:
                # 打印請求詳細信息以進行調試
                logger.info(f"Making request to chatapi.littlewheat.com with model: {model_name} (attempt {retry_count + 1}/{max_retries})")
                
                # 設置到特定 API 端點的連接
                conn = http.client.HTTPSConnection("chatapi.littlewheat.com", timeout=30)
                
                # 準備流式處理的有效載荷
                payload = json.dumps({
                    "model": model_name,
                    "messages": messages,
                    "stream": True,
                    "temperature": 0.7,
                    "max_tokens": 1000
                })
                
                # 設置帶有 API 密鑰的標頭
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                }
                
                # 進行流式 API 請求
                conn.request("POST", "/v1/chat/completions", payload, headers)
                response = conn.getresponse()
                
                # 檢查錯誤
                if response.status != 200:
                    error_data = response.read().decode('utf-8', errors='replace')
                    error_msg = f"Grok API returned error {response.status}: {error_data}"
                    
                    # 如果是伺服器錯誤 (5xx)，重試
                    if 500 <= response.status < 600:
                        retry_count += 1
                        if retry_count < max_retries:
                            logger.warning(f"Server error {response.status}, retrying in {retry_delay} seconds...")
                            time.sleep(retry_delay)
                            retry_delay *= 2  # 指數退避
                            continue
                    
                    # 如果我們已經用盡重試或者是客戶端錯誤，則產生錯誤消息
                    yield error_msg
                    return
                
                # 處理流式響應
                collected_content = ""
                buffer = ""
                
                # 一次讀取更大的塊而不是逐字節讀取，以避免 UTF-8 解碼問題
                while True:
                    chunk = response.read(4096)  # 一次讀取 4KB
                    if not chunk:
                        break
                    
                    # 使用錯誤處理進行解碼
                    try:
                        text = chunk.decode('utf-8', errors='replace')
                        buffer += text
                    except Exception as e:
                        logger.warning(f"Warning: Error decoding chunk: {e}")
                        continue
                    
                    # 處理完整行
                    while '\n' in buffer:
                        pos = buffer.find('\n')
                        line = buffer[:pos]
                        buffer = buffer[pos + 1:]
                        
                        if not line.strip():
                            continue
                        
                        if line.startswith('data: '):
                            line = line[6:].strip()  # 跳過 "data: " 前綴
                            
                            if line == '[DONE]':
                                # 完整響應的最終生成
                                if collected_content:
                                    yield collected_content
                                return
                            
                            try:
                                json_response = json.loads(line)
                                if "choices" in json_response and json_response["choices"]:
                                    delta = json_response["choices"][0].get("delta", {})
                                    if "content" in delta and delta["content"]:
                                        new_content = delta["content"]
                                        collected_content += new_content
                                        yield collected_content
                            except json.JSONDecodeError as je:
                                logger.warning(f"Warning: JSON decode error: {je}. Input: {line[:100]}...")
                                continue
                
                # 處理緩衝區中的任何剩餘數據
                if buffer.strip():
                    for line in buffer.strip().split('\n'):
                        if line.startswith('data: '):
                            line = line[6:].strip()
                            
                            if line == '[DONE]':
                                break
                            
                            try:
                                json_response = json.loads(line)
                                if "choices" in json_response and json_response["choices"]:
                                    delta = json_response["choices"][0].get("delta", {})
                                    if "content" in delta and delta["content"]:
                                        new_content = delta["content"]
                                        collected_content += new_content
                            except json.JSONDecodeError:
                                continue
                                
                # 確保我們生成最終內容
                if collected_content:
                    yield collected_content
                    return
                    
            except http.client.HTTPException as e:
                retry_count += 1
                if retry_count < max_retries:
                    logger.warning(f"HTTP error: {e}, retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # 指數退避
                    continue
                else:
                    logger.error(f"HTTP error after {max_retries} attempts: {e}")
                    yield f"Error connecting to Grok API after {max_retries} attempts: {str(e)}"
                    return
                    
            except Exception as e:
                import traceback
                logger.error(f"Error streaming from Grok API: {str(e)}")
                logger.error(traceback.format_exc())
                yield f"Error streaming from Grok API: {str(e)}"
                return 