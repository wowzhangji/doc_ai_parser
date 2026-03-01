"""请求模型定义"""

from typing import Any, Dict, List, Literal, Optional
from pathlib import Path
from pydantic import BaseModel, Field


class ExtractionRule(BaseModel):
    """提取规则"""
    field_name: str
    description: str
    required: bool = True
    data_type: str = "string"
    example: Optional[Any] = None


class DocumentSource(BaseModel):
    """文档来源"""
    file_path: Optional[Path] = None
    file_content: Optional[bytes] = None
    file_type: Literal["pdf", "docx", "xlsx", "txt", "md"] = Field(..., description="文件类型")


class RequirementDoc(BaseModel):
    """解析要求文档"""
    content: str = Field(..., description="要求说明文本")
    output_schema: Dict[str, Any] = Field(default_factory=dict, description="期望的输出JSON Schema")
    extraction_rules: List[ExtractionRule] = Field(default_factory=list, description="提取规则列表")


class ParseConfig(BaseModel):
    """解析配置"""
    provider: Literal[
        "openai", 
        "azure", 
        "anthropic", 
        "custom_openai", 
        "custom_anthropic", 
        "ollama"
    ] = Field(default="openai", description="LLM提供商")
    model: Optional[str] = Field(default=None, description="模型名称")
    api_base: Optional[str] = Field(default=None, description="自定义API基础URL")
    api_key: Optional[str] = Field(default=None, description="API密钥")
    chunk_size: int = Field(default=3000, description="分块大小（token数）")
    chunk_overlap: int = Field(default=200, description="分块重叠大小")
    temperature: float = Field(default=0.1, description="模型温度参数")
    max_retries: int = Field(default=3, description="最大重试次数")
    use_cache: bool = Field(default=True, description="是否使用缓存")


class ParseRequest(BaseModel):
    """解析请求"""
    source_document: DocumentSource
    requirement_doc: RequirementDoc
    config: Optional[ParseConfig] = Field(default_factory=ParseConfig)
    previous_result: Optional[Dict[str, Any]] = Field(default=None, description="之前的解析结果（用于增量更新）")
