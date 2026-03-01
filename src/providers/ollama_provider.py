"""Ollama本地模型提供商实现"""

from typing import Any, Dict, Optional

import httpx

from src.models.document import Chunk
from src.models.request import RequirementDoc
from src.providers.base import LLMProvider, ProviderConfig
from src.config import settings


class OllamaProvider(LLMProvider):
    """Ollama本地模型提供商"""
    
    DEFAULT_MODEL = "llama2"
    
    def __init__(self, config: Optional[ProviderConfig] = None):
        if config is None:
            config = ProviderConfig(
                base_url=settings.ollama_base_url,
                model=settings.ollama_default_model,
                temperature=settings.default_temperature,
            )
        super().__init__(config)
        
        self.base_url = (config.base_url or settings.ollama_base_url).rstrip('/')
        self.timeout = config.timeout
    
    def get_default_model(self) -> str:
        return self.config.model or self.DEFAULT_MODEL
    
    async def parse(
        self,
        chunk: Chunk,
        requirement: RequirementDoc,
        output_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """使用Ollama本地模型解析文档片段"""
        model = self.get_default_model()
        
        system_prompt = self.build_system_prompt(requirement)
        user_prompt = self.build_user_prompt(chunk, requirement, output_schema)
        
        # Ollama使用组合prompt
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        payload = {
            "model": model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                content = data.get("response", "")
                
                self.logger.info(
                    "ollama_parse_success",
                    model=model,
                    chunk_index=chunk.index,
                    total_duration=data.get("total_duration"),
                )
                
                return self.parse_json_response(content)
                
        except httpx.HTTPStatusError as e:
            self.logger.error(
                "ollama_http_error",
                status_code=e.response.status_code,
                response=e.response.text,
                chunk_index=chunk.index,
            )
            raise
        except Exception as e:
            self.logger.error(
                "ollama_parse_error",
                error=str(e),
                chunk_index=chunk.index,
            )
            raise
    
    async def list_models(self) -> list:
        """列出本地可用的模型"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
                return data.get("models", [])
        except Exception as e:
            self.logger.warning("failed_to_list_ollama_models", error=str(e))
            return []
    
    async def pull_model(self, model_name: str) -> bool:
        """拉取模型"""
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/pull",
                    json={"name": model_name, "stream": False}
                )
                response.raise_for_status()
                return True
        except Exception as e:
            self.logger.error("failed_to_pull_model", error=str(e), model=model_name)
            return False
