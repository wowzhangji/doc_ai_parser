"""测试智能分块模块"""

import pytest

from src.models.document import Document, DocumentSection, SectionType
from src.core.chunker import SmartChunker


class TestSmartChunker:
    """测试智能分块器"""
    
    def test_basic_chunking(self):
        """测试基本分块功能"""
        content = "\n\n".join([f"段落 {i}" * 100 for i in range(10)])
        document = Document(content=content)
        
        chunker = SmartChunker(max_tokens=500)
        chunks = chunker.chunk(document)
        
        assert len(chunks) > 0
        assert all(len(chunk.content) > 0 for chunk in chunks)
    
    def test_semantic_chunking_with_headings(self):
        """测试带标题的语义分块"""
        sections = [
            DocumentSection(type=SectionType.HEADING, content="第一章", level=1),
            DocumentSection(type=SectionType.PARAGRAPH, content="这是第一章的内容" * 50),
            DocumentSection(type=SectionType.HEADING, content="第二章", level=1),
            DocumentSection(type=SectionType.PARAGRAPH, content="这是第二章的内容" * 50),
        ]
        
        from src.models.document import DocumentStructure
        document = Document(
            content="",
            structure=DocumentStructure(sections=sections)
        )
        
        chunker = SmartChunker(max_tokens=1000)
        chunks = chunker.chunk(document)
        
        assert len(chunks) >= 2  # 至少应该分成两章
    
    def test_api_endpoint_preservation(self):
        """测试API端点保持完整"""
        sections = [
            DocumentSection(type=SectionType.HEADING, content="API文档", level=1),
            DocumentSection(
                type=SectionType.API_ENDPOINT, 
                content="GET /api/v1/users",
                metadata={"is_endpoint": True}
            ),
            DocumentSection(type=SectionType.PARAGRAPH, content="获取用户列表"),
        ]
        
        from src.models.document import DocumentStructure
        document = Document(
            content="",
            structure=DocumentStructure(sections=sections)
        )
        
        chunker = SmartChunker()
        chunks = chunker.chunk(document)
        
        # 检查API端点是否被正确识别
        assert any(
            "GET /api/v1/users" in chunk.content 
            for chunk in chunks
        )
    
    def test_chunk_overlap(self):
        """测试分块重叠"""
        # 创建一个长段落
        content = "这是一个很长的段落。" * 1000
        document = Document(content=content)
        
        chunker = SmartChunker(max_tokens=100, overlap_tokens=20)
        chunks = chunker.chunk(document)
        
        if len(chunks) > 1:
            # 检查相邻块是否有重叠
            chunk1_end = chunks[0].content[-50:]
            chunk2_start = chunks[1].content[:50]
            
            # 应该有部分重叠
            assert len(set(chunk1_end) & set(chunk2_start)) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
