"""LLM提供商工厂"""

from typing import Optional

from src.providers.base import LLMProvider, ProviderConfig
from src.providers.openai_provider import OpenAIProvider
from src.providers.azure_provider import AzureOpenAIProvider
from src.providers.anthropic_provider import AnthropicProvider
from src.providers.custom_openai_provider import CustomOpenAIProvider
from src.providers.custom_anthropic_provider import CustomAnthropicProvider
from src.providers.ollama_provider import OllamaProvider


def get_provider(
    provider_name: str,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.1,
    max_retries: int = 3,
) -> LLMProvider:
    """
    获取LLM提供商实例
    
    Args:
        provider_name: 提供商名称
            - openai: OpenAI官方API
            - azure: Azure OpenAI
            - anthropic: Anthropic Claude
            - custom_openai: 自定义OpenAI协议API
            - custom_anthropic: 自定义Anthropic协议API
            - ollama: Ollama本地模型
        api_key: API密钥
        api_base: API基础URL
        model: 模型名称
        temperature: 温度参数
        max_retries: 最大重试次数
        
    Returns:
        LLMProvider实例
    """
    config = ProviderConfig(
        api_key=api_key,
        base_url=api_base,
        model=model,
        temperature=temperature,
        max_retries=max_retries,
    )
    
    providers = {
        "openai": OpenAIProvider,
        "azure": AzureOpenAIProvider,
        "anthropic": AnthropicProvider,
        "custom_openai": CustomOpenAIProvider,
        "custom_anthropic": CustomAnthropicProvider,
        "ollama": OllamaProvider,
    }
    
    provider_class = providers.get(provider_name.lower())
    if not provider_class:
        raise ValueError(
            f"未知的提供商: {provider_name}. "
            f"支持的提供商: {', '.join(providers.keys())}"
        )
    
    # 自定义提供商需要base_url
    if provider_name in ("custom_openai", "custom_anthropic") and not api_base:
        raise ValueError(f"{provider_name} 需要提供 api_base 参数")
    
    return provider_class(config)
