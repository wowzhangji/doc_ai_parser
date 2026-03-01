"""自定义OpenAI协议API提供商 - 支持vLLM、TGI等"""

from typing import Any, Dict, Optional

import httpx

from src.models.document import Chunk
from src.models.request import RequirementDoc
from src.providers.base import LLMProvider, ProviderConfig


class CustomOpenAIProvider(LLMProvider):
    """
    自定义OpenAI协议API提供商
    
    支持任何兼容OpenAI API协议的自定义端点，如：
    - vLLM
    - Text Generation Inference (TGI)
    - LocalAI
    - 其他OpenAI兼容API
    """
    
    def __init__(self, config: ProviderConfig):
        if not config.base_url:
            raise ValueError("Custom OpenAI provider requires base_url")
        super().__init__(config)
        
        self.base_url = config.base_url.rstrip('/')
        self.api_key = config.api_key or "not-needed"
        self.timeout = config.timeout
    
    def get_default_model(self) -> str:
        return self.config.model or "default"
    
    async def parse(
        self,
        chunk: Chunk,
        requirement: RequirementDoc,
        output_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """使用自定义OpenAI协议API解析文档片段"""
        model = self.get_default_model()
        
        system_prompt = self.build_system_prompt(requirement)
        user_prompt = self.build_user_prompt(chunk, requirement, output_schema)
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": self.config.temperature,
            "max_tokens": 4096,
        }
        
        # 如果API支持，请求JSON格式输出
        # 注意：不是所有自定义API都支持response_format
        # payload["response_format"] = {"type": "json_object"}
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                
                self.logger.info(
                    "custom_openai_parse_success",
                    base_url=self.base_url,
                    model=model,
                    chunk_index=chunk.index,
                )
                
                return self.parse_json_response(content)
                
        except httpx.HTTPStatusError as e:
            self.logger.error(
                "custom_openai_http_error",
                status_code=e.response.status_code,
                response=e.response.text,
                chunk_index=chunk.index,
            )
            raise
        except Exception as e:
            self.logger.error(
                "custom_openai_parse_error",
                error=str(e),
                base_url=self.base_url,
                chunk_index=chunk.index,
            )
            raise
    
    async def list_models(self) -> list:
        """列出可用的模型"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers=headers
                )
                response.raise_for_status()
                data = response.json()
                return data.get("data", [])
        except Exception as e:
            self.logger.warning("failed_to_list_models", error=str(e))
            return []
