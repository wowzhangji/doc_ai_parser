"""自定义Anthropic协议API提供商"""

from typing import Any, Dict, Optional

import httpx

from src.models.document import Chunk
from src.models.request import RequirementDoc
from src.providers.base import LLMProvider, ProviderConfig


class CustomAnthropicProvider(LLMProvider):
    """
    自定义Anthropic协议API提供商
    
    支持任何兼容Anthropic Messages API协议的自定义端点
    """
    
    def __init__(self, config: ProviderConfig):
        if not config.base_url:
            raise ValueError("Custom Anthropic provider requires base_url")
        super().__init__(config)
        
        self.base_url = config.base_url.rstrip('/')
        self.api_key = config.api_key or "not-needed"
        self.timeout = config.timeout
    
    def get_default_model(self) -> str:
        return self.config.model or "claude-3-sonnet"
    
    async def parse(
        self,
        chunk: Chunk,
        requirement: RequirementDoc,
        output_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """使用自定义Anthropic协议API解析文档片段"""
        model = self.get_default_model()
        
        system_prompt = self.build_system_prompt(requirement)
        user_prompt = self.build_user_prompt(chunk, requirement, output_schema)
        
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        
        payload = {
            "model": model,
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt}
            ],
            "temperature": self.config.temperature,
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                content = data["content"][0]["text"]
                
                self.logger.info(
                    "custom_anthropic_parse_success",
                    base_url=self.base_url,
                    model=model,
                    chunk_index=chunk.index,
                )
                
                return self.parse_json_response(content)
                
        except httpx.HTTPStatusError as e:
            self.logger.error(
                "custom_anthropic_http_error",
                status_code=e.response.status_code,
                response=e.response.text,
                chunk_index=chunk.index,
            )
            raise
        except Exception as e:
            self.logger.error(
                "custom_anthropic_parse_error",
                error=str(e),
                base_url=self.base_url,
                chunk_index=chunk.index,
            )
            raise
