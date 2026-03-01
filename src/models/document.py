"""文档模型定义"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class SectionType(Enum):
    """文档章节类型"""
    TITLE = "title"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    CODE = "code"
    LIST = "list"
    API_ENDPOINT = "api_endpoint"
    UNKNOWN = "unknown"


@dataclass
class DocumentSection:
    """文档章节"""
    type: SectionType
    content: str
    level: int = 0  # 标题层级
    metadata: Dict[str, Any] = field(default_factory=dict)
    children: List["DocumentSection"] = field(default_factory=list)


@dataclass
class DocumentStructure:
    """文档结构信息"""
    sections: List[DocumentSection] = field(default_factory=list)
    headings: List[Dict[str, Any]] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    
    def get_api_sections(self) -> List[DocumentSection]:
        """获取API相关的章节"""
        return [s for s in self.sections if s.type == SectionType.API_ENDPOINT]


@dataclass
class Document:
    """文档对象"""
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    structure: Optional[DocumentStructure] = None
    file_type: Optional[str] = None
    file_path: Optional[str] = None
    
    def __post_init__(self):
        if self.structure is None:
            self.structure = DocumentStructure()


@dataclass
class Chunk:
    """文档分块"""
    content: str = ""
    index: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    sections: List[DocumentSection] = field(default_factory=list)
    context: str = ""  # 上下文信息
    
    def add_section(self, section: DocumentSection) -> None:
        """添加章节到chunk"""
        self.sections.append(section)
        if self.content:
            self.content += "\n\n"
        self.content += section.content
    
    def estimate_tokens(self) -> int:
        """估算token数量（简单估算：1token ≈ 4字符）"""
        return len(self.content) // 4
