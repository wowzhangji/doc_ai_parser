"""Azure OpenAI提供商实现"""

from typing import Any, Dict, Optional

from openai import AsyncAzureOpenAI

from src.models.document import Chunk
from src.models.request import RequirementDoc
from src.providers.base import LLMProvider, ProviderConfig
from src.config import settings


class AzureOpenAIProvider(LLMProvider):
    """Azure OpenAI服务提供商"""
    
    DEFAULT_MODEL = "gpt-4"
    
    def __init__(self, config: Optional[ProviderConfig] = None):
        if config is None:
            config = ProviderConfig(
                api_key=settings.azure_openai_api_key,
                base_url=settings.azure_openai_endpoint,
                model=settings.azure_openai_default_model,
                temperature=settings.default_temperature,
                max_retries=settings.max_retries,
            )
        super().__init__(config)
        
        if not config.base_url:
            raise ValueError("Azure OpenAI requires endpoint (base_url)")
        
        self.client = AsyncAzureOpenAI(
            api_key=config.api_key,
            azure_endpoint=config.base_url,
            api_version=settings.azure_openai_api_version,
            max_retries=config.max_retries,
        )
    
    def get_default_model(self) -> str:
        return self.config.model or self.DEFAULT_MODEL
    
    async def parse(
        self,
        chunk: Chunk,
        requirement: RequirementDoc,
        output_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """使用Azure OpenAI解析文档片段"""
        model = self.get_default_model()
        
        system_prompt = self.build_system_prompt(requirement)
        user_prompt = self.build_user_prompt(chunk, requirement, output_schema)
        
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.config.temperature,
                response_format={"type": "json_object"},
            )
            
            content = response.choices[0].message.content
            
            self.logger.info(
                "azure_openai_parse_success",
                model=model,
                chunk_index=chunk.index,
                tokens_used=response.usage.total_tokens if response.usage else None,
            )
            
            return self.parse_json_response(content)
            
        except Exception as e:
            self.logger.error(
                "azure_openai_parse_error",
                error=str(e),
                chunk_index=chunk.index,
            )
            raise
