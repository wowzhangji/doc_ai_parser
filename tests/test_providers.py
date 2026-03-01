"""测试LLM提供商"""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from src.providers.base import ProviderConfig
from src.providers.openai_provider import OpenAIProvider
from src.providers.anthropic_provider import AnthropicProvider
from src.providers.custom_openai_provider import CustomOpenAIProvider
from src.providers.factory import get_provider


class TestProviderFactory:
    """测试提供商工厂"""
    
    def test_get_openai_provider(self):
        """测试获取OpenAI提供商"""
        config = ProviderConfig(api_key="test-key")
        provider = get_provider("openai", api_key="test-key")
        assert isinstance(provider, OpenAIProvider)
    
    def test_get_anthropic_provider(self):
        """测试获取Anthropic提供商"""
        provider = get_provider("anthropic", api_key="test-key")
        assert isinstance(provider, AnthropicProvider)
    
    def test_get_custom_openai_provider_requires_base(self):
        """测试自定义OpenAI提供商需要base_url"""
        with pytest.raises(ValueError, match="custom_openai 需要提供 api_base 参数"):
            get_provider("custom_openai")
    
    def test_get_custom_openai_provider(self):
        """测试获取自定义OpenAI提供商"""
        provider = get_provider(
            "custom_openai",
            api_base="http://localhost:8000/v1",
            api_key="test-key"
        )
        assert isinstance(provider, CustomOpenAIProvider)
    
    def test_get_unknown_provider(self):
        """测试获取未知提供商"""
        with pytest.raises(ValueError, match="未知的提供商"):
            get_provider("unknown_provider")


class TestOpenAIProvider:
    """测试OpenAI提供商"""
    
    @pytest.mark.asyncio
    async def test_parse(self):
        """测试解析功能"""
        config = ProviderConfig(api_key="test-key", model="gpt-4")
        provider = OpenAIProvider(config)
        
        # Mock客户端
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='{"result": "test"}'))]
        mock_response.usage = Mock(total_tokens=100)
        
        provider.client = Mock()
        provider.client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        from src.models.document import Chunk
        from src.models.request import RequirementDoc
        
        chunk = Chunk(content="测试内容", index=0)
        requirement = RequirementDoc(content="提取信息")
        
        result = await provider.parse(chunk, requirement)
        
        assert "result" in result
        assert result["result"] == "test"


class TestAnthropicProvider:
    """测试Anthropic提供商"""
    
    @pytest.mark.asyncio
    async def test_parse(self):
        """测试解析功能"""
        config = ProviderConfig(api_key="test-key", model="claude-3-sonnet")
        provider = AnthropicProvider(config)
        
        # Mock客户端
        mock_response = Mock()
        mock_response.content = [Mock(text='{"result": "test"}')]
        mock_response.usage = Mock(input_tokens=50, output_tokens=50)
        
        provider.client = Mock()
        provider.client.messages.create = AsyncMock(return_value=mock_response)
        
        from src.models.document import Chunk
        from src.models.request import RequirementDoc
        
        chunk = Chunk(content="测试内容", index=0)
        requirement = RequirementDoc(content="提取信息")
        
        result = await provider.parse(chunk, requirement)
        
        assert "result" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
