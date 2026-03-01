"""配置管理模块"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # 应用配置
    app_name: str = "API Doc Parser"
    debug: bool = False
    
    # OpenAI配置
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    openai_default_model: str = "gpt-4"
    
    # Azure OpenAI配置
    azure_openai_api_key: Optional[str] = None
    azure_openai_endpoint: Optional[str] = None
    azure_openai_api_version: str = "2024-02-01"
    azure_openai_default_model: str = "gpt-4"
    
    # Anthropic配置
    anthropic_api_key: Optional[str] = None
    anthropic_base_url: Optional[str] = None
    anthropic_default_model: str = "claude-3-5-sonnet-20241022"
    
    # Ollama配置
    ollama_base_url: str = "http://localhost:11434"
    ollama_default_model: str = "llama2"
    
    # Redis配置（用于Celery）
    redis_url: str = "redis://localhost:6379/0"
    
    # 解析配置
    default_chunk_size: int = 3000
    default_chunk_overlap: int = 200
    default_temperature: float = 0.1
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # 文件上传配置
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    upload_dir: str = "./uploads"


# 全局配置实例
settings = Settings()
