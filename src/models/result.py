"""结果模型定义"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ParseMetadata(BaseModel):
    """解析元数据"""
    total_chunks: int = Field(default=0, description="总分块数")
    processed_chunks: int = Field(default=0, description="已处理分块数")
    failed_chunks: List[int] = Field(default_factory=list, description="失败的分块索引")
    confidence_score: float = Field(default=0.0, description="整体置信度")
    warnings: List[str] = Field(default_factory=list, description="警告信息")
    processing_time: Optional[float] = Field(default=None, description="处理时间（秒）")
    model_used: Optional[str] = Field(default=None, description="使用的模型")
    provider_used: Optional[str] = Field(default=None, description="使用的提供商")


class ParseResult(BaseModel):
    """解析结果"""
    version: str = Field(default="1.0", description="结果版本")
    parsed_at: datetime = Field(default_factory=datetime.now, description="解析时间")
    source_fingerprint: Optional[str] = Field(default=None, description="源文档指纹")
    
    # 动态结构，基于requirement_doc.output_schema
    data: Dict[str, Any] = Field(default_factory=dict, description="解析后的结构化数据")
    
    metadata: ParseMetadata = Field(default_factory=ParseMetadata, description="解析元数据")
    
    # 增量更新相关
    is_incremental: bool = Field(default=False, description="是否为增量更新")
    changed_fields: List[str] = Field(default_factory=list, description="变更的字段")
    
    def merge(self, other: "ParseResult") -> "ParseResult":
        """合并另一个解析结果"""
        merged_data = {**self.data, **other.data}
        merged_warnings = list(set(self.metadata.warnings + other.metadata.warnings))
        
        return ParseResult(
            version=self.version,
            parsed_at=datetime.now(),
            source_fingerprint=other.source_fingerprint or self.source_fingerprint,
            data=merged_data,
            metadata=ParseMetadata(
                total_chunks=self.metadata.total_chunks + other.metadata.total_chunks,
                processed_chunks=self.metadata.processed_chunks + other.metadata.processed_chunks,
                failed_chunks=list(set(self.metadata.failed_chunks + other.metadata.failed_chunks)),
                confidence_score=(self.metadata.confidence_score + other.metadata.confidence_score) / 2,
                warnings=merged_warnings,
            ),
            is_incremental=True,
            changed_fields=list(other.data.keys())
        )
