"""Anthropic Claude提供商实现"""

from typing import Any, Dict, Optional

from anthropic import AsyncAnthropic

from src.models.document import Chunk
from src.models.request import RequirementDoc
from src.providers.base import LLMProvider, ProviderConfig
from src.config import settings


class AnthropicProvider(LLMProvider):
    """Anthropic Claude官方API提供商"""
    
    DEFAULT_MODEL = "claude-3-5-sonnet-20241022"
    
    def __init__(self, config: Optional[ProviderConfig] = None):
        if config is None:
            config = ProviderConfig(
                api_key=settings.anthropic_api_key,
                base_url=settings.anthropic_base_url,
                model=settings.anthropic_default_model,
                temperature=settings.default_temperature,
                max_retries=settings.max_retries,
            )
        super().__init__(config)
        
        client_kwargs = {
            "api_key": config.api_key,
        }
        if config.base_url:
            client_kwargs["base_url"] = config.base_url
            
        self.client = AsyncAnthropic(**client_kwargs)
    
    def get_default_model(self) -> str:
        return self.config.model or self.DEFAULT_MODEL
    
    async def parse(
        self,
        chunk: Chunk,
        requirement: RequirementDoc,
        output_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """使用Anthropic Claude解析文档片段"""
        model = self.get_default_model()
        
        system_prompt = self.build_system_prompt(requirement)
        user_prompt = self.build_user_prompt(chunk, requirement, output_schema)
        
        # Claude的system prompt通过单独的参数传递
        try:
            response = await self.client.messages.create(
                model=model,
                max_tokens=4096,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.config.temperature,
            )
            
            content = response.content[0].text
            
            self.logger.info(
                "anthropic_parse_success",
                model=model,
                chunk_index=chunk.index,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens if response.usage else None,
            )
            
            return self.parse_json_response(content)
            
        except Exception as e:
            self.logger.error(
                "anthropic_parse_error",
                error=str(e),
                chunk_index=chunk.index,
            )
            raise
