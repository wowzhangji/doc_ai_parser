"""智能分块模块 - 结构感知 + 长度限制 + 重叠缓冲"""

import re
from typing import List, Optional, Tuple

from src.models.document import Document, Chunk, DocumentSection, SectionType
from src.config import settings


class SmartChunker:
    """智能文档分块器"""
    
    def __init__(
        self,
        max_tokens: int = None,
        overlap_tokens: int = None,
        preserve_structures: bool = True
    ):
        self.max_tokens = max_tokens or settings.default_chunk_size
        self.overlap_tokens = overlap_tokens or settings.default_chunk_overlap
        self.preserve_structures = preserve_structures
        
        # 估算：1 token ≈ 4 字符（中文）
        self.chars_per_token = 4
        self.max_chars = self.max_tokens * self.chars_per_token
        self.overlap_chars = self.overlap_tokens * self.chars_per_token
    
    def chunk(self, document: Document) -> List[Chunk]:
        """
        对文档进行智能分块
        
        策略：
        1. 首先按文档结构（标题、章节、API端点）进行语义分块
        2. 对过大的块进行细粒度分割（滑动窗口）
        3. 保持块间重叠，避免信息截断
        """
        if not document.structure or not document.structure.sections:
            # 没有结构信息，按纯文本分块
            return self._chunk_by_text(document.content)
        
        # 1. 语义分块
        semantic_chunks = self._semantic_chunk(document)
        
        # 2. 处理过大的块
        final_chunks = []
        for i, chunk in enumerate(semantic_chunks):
            if self._estimate_tokens(chunk.content) > self.max_tokens:
                # 大块使用滑动窗口细分
                sub_chunks = self._sliding_window_split(chunk)
                for j, sub_chunk in enumerate(sub_chunks):
                    sub_chunk.index = len(final_chunks)
                    sub_chunk.metadata["parent_chunk"] = i
                    sub_chunk.metadata["sub_chunk"] = j
                    final_chunks.append(sub_chunk)
            else:
                chunk.index = len(final_chunks)
                final_chunks.append(chunk)
        
        # 3. 为每个块添加上下文
        self._add_context(final_chunks, document)
        
        return final_chunks
    
    def _semantic_chunk(self, document: Document) -> List[Chunk]:
        """基于文档结构的语义分块"""
        chunks = []
        current_chunk = Chunk()
        current_sections = []
        
        sections = document.structure.sections
        
        for i, section in enumerate(sections):
            section_text = section.content
            section_tokens = self._estimate_tokens(section_text)
            
            # 判断是否需要开始新chunk
            should_new_chunk = False
            
            # 规则1：遇到API端点，开始新chunk（保持API信息完整）
            if section.type == SectionType.API_ENDPOINT:
                should_new_chunk = True
            
            # 规则2：遇到一级标题，开始新chunk
            if section.type == SectionType.HEADING and section.level == 1:
                should_new_chunk = True
            
            # 规则3：当前chunk已满
            current_tokens = self._estimate_tokens(current_chunk.content)
            if current_tokens + section_tokens > self.max_tokens:
                should_new_chunk = True
            
            # 规则4：表格和代码块尽量保持完整
            if section.type in (SectionType.TABLE, SectionType.CODE):
                if section_tokens > self.max_tokens * 0.8:
                    # 表格/代码块太大，需要特殊处理
                    if current_chunk.content:
                        current_chunk.sections = current_sections
                        chunks.append(current_chunk)
                    
                    # 单独处理大表格/代码块
                    table_chunks = self._split_large_section(section)
                    chunks.extend(table_chunks)
                    
                    current_chunk = Chunk()
                    current_sections = []
                    continue
            
            if should_new_chunk and current_chunk.content:
                current_chunk.sections = current_sections
                chunks.append(current_chunk)
                current_chunk = Chunk()
                current_sections = []
            
            current_sections.append(section)
            if current_chunk.content:
                current_chunk.content += "\n\n"
            current_chunk.content += section_text
            current_chunk.metadata["section_types"] = current_chunk.metadata.get("section_types", []) + [section.type.value]
        
        # 添加最后一个chunk
        if current_chunk.content:
            current_chunk.sections = current_sections
            chunks.append(current_chunk)
        
        return chunks
    
    def _chunk_by_text(self, text: str) -> List[Chunk]:
        """纯文本分块（无结构信息时）"""
        chunks = []
        
        # 尝试按段落分割
        paragraphs = text.split('\n\n')
        current_chunk = Chunk()
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            para_tokens = self._estimate_tokens(para)
            current_tokens = self._estimate_tokens(current_chunk.content)
            
            if current_tokens + para_tokens > self.max_tokens and current_chunk.content:
                chunks.append(current_chunk)
                current_chunk = Chunk()
            
            if current_chunk.content:
                current_chunk.content += "\n\n"
            current_chunk.content += para
        
        if current_chunk.content:
            chunks.append(current_chunk)
        
        # 如果chunk还太大，使用滑动窗口
        final_chunks = []
        for chunk in chunks:
            if self._estimate_tokens(chunk.content) > self.max_tokens:
                sub_chunks = self._sliding_window_split(chunk)
                final_chunks.extend(sub_chunks)
            else:
                chunk.index = len(final_chunks)
                final_chunks.append(chunk)
        
        return final_chunks
    
    def _sliding_window_split(self, chunk: Chunk) -> List[Chunk]:
        """使用滑动窗口分割大chunk"""
        chunks = []
        content = chunk.content
        
        # 尝试在句子边界分割
        sentences = self._split_to_sentences(content)
        
        current_chunk = Chunk()
        current_chunk.metadata = chunk.metadata.copy()
        current_sections = []
        
        for sentence in sentences:
            sentence_tokens = self._estimate_tokens(sentence)
            current_tokens = self._estimate_tokens(current_chunk.content)
            
            if current_tokens + sentence_tokens > self.max_tokens and current_chunk.content:
                current_chunk.sections = current_sections
                chunks.append(current_chunk)
                
                # 创建新chunk，保留重叠部分
                overlap_text = self._get_overlap_text(current_chunk.content)
                current_chunk = Chunk()
                current_chunk.metadata = chunk.metadata.copy()
                current_chunk.content = overlap_text
                current_sections = []
            
            if current_chunk.content:
                current_chunk.content += " "
            current_chunk.content += sentence
        
        if current_chunk.content:
            current_chunk.sections = current_sections
            chunks.append(current_chunk)
        
        return chunks
    
    def _split_large_section(self, section: DocumentSection) -> List[Chunk]:
        """分割大的表格或代码块"""
        chunks = []
        content = section.content
        
        # 按行分割
        lines = content.split('\n')
        current_chunk = Chunk()
        current_chunk.metadata["section_type"] = section.type.value
        
        for line in lines:
            line_tokens = self._estimate_tokens(line)
            current_tokens = self._estimate_tokens(current_chunk.content)
            
            if current_tokens + line_tokens > self.max_tokens and current_chunk.content:
                chunks.append(current_chunk)
                
                # 保留表头或代码开头作为重叠
                overlap = self._get_structure_prefix(content, section.type)
                current_chunk = Chunk()
                current_chunk.metadata["section_type"] = section.type.value
                current_chunk.content = overlap
            
            if current_chunk.content:
                current_chunk.content += "\n"
            current_chunk.content += line
        
        if current_chunk.content:
            chunks.append(current_chunk)
        
        return chunks
    
    def _split_to_sentences(self, text: str) -> List[str]:
        """将文本分割为句子"""
        # 简单的句子分割（中英文）
        sentence_endings = r'([。！？.!?]\s*)'
        sentences = re.split(sentence_endings, text)
        
        # 合并分割符和前一句
        result = []
        for i in range(0, len(sentences) - 1, 2):
            if i + 1 < len(sentences):
                result.append(sentences[i] + sentences[i + 1])
            else:
                result.append(sentences[i])
        
        if len(sentences) % 2 == 1:
            result.append(sentences[-1])
        
        return [s.strip() for s in result if s.strip()]
    
    def _get_overlap_text(self, content: str) -> str:
        """获取重叠文本（从末尾截取）"""
        # 取最后overlap_chars个字符，但尽量在句子边界
        if len(content) <= self.overlap_chars:
            return content
        
        overlap_start = len(content) - self.overlap_chars
        # 尝试找到句子开始位置
        search_start = max(0, overlap_start - 100)
        substring = content[search_start:overlap_start + self.overlap_chars]
        
        # 找第一个句子结束后的位置
        sentence_match = re.search(r'[。！？.!?]\s+', substring)
        if sentence_match:
            actual_start = search_start + sentence_match.end()
            return content[actual_start:]
        
        return content[overlap_start:]
    
    def _get_structure_prefix(self, content: str, section_type: SectionType) -> str:
        """获取结构前缀（表头或代码声明）"""
        lines = content.split('\n')
        
        if section_type == SectionType.TABLE:
            # 保留表头（通常是前两行）
            return '\n'.join(lines[:2]) if len(lines) >= 2 else content[:200]
        elif section_type == SectionType.CODE:
            # 保留代码声明/注释
            prefix_lines = []
            for line in lines:
                if line.strip().startswith('#') or line.strip().startswith('//'):
                    prefix_lines.append(line)
                else:
                    break
            return '\n'.join(prefix_lines) if prefix_lines else lines[0] if lines else ""
        
        return ""
    
    def _add_context(self, chunks: List[Chunk], document: Document) -> None:
        """为每个块添加上下文信息"""
        if not chunks:
            return
        
        # 提取文档全局信息
        global_info = self._extract_global_info(document)
        
        for i, chunk in enumerate(chunks):
            context_parts = [global_info]
            
            # 添加相邻chunks的摘要
            neighbors = self._get_neighbor_chunks(chunks, i, radius=1)
            for neighbor_idx, neighbor in neighbors:
                if neighbor_idx != i:
                    summary = self._summarize_chunk(neighbor)
                    context_parts.append(f"[相邻片段 {neighbor_idx + 1}]: {summary}")
            
            chunk.context = "\n\n".join(context_parts)
    
    def _extract_global_info(self, document: Document) -> str:
        """提取文档全局信息"""
        info_parts = ["【文档全局信息】"]
        
        # 提取可能的API基础URL
        content = document.content
        url_pattern = r'https?://[^\s<>"{}|\\^`[\]]+'
        urls = re.findall(url_pattern, content[:5000])
        if urls:
            info_parts.append(f"可能的API基础URL: {urls[0]}")
        
        # 提取认证信息
        auth_patterns = [
            r'(API Key|Token|认证|Authorization)[：:]\s*([^\n]+)',
            r'(Bearer|Basic)\s+',
        ]
        for pattern in auth_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                info_parts.append(f"认证方式: {match.group(0)}")
                break
        
        # 提取文档标题
        if document.structure and document.structure.sections:
            first_section = document.structure.sections[0]
            if first_section.type == SectionType.HEADING:
                info_parts.append(f"文档标题: {first_section.content}")
        
        return "\n".join(info_parts)
    
    def _get_neighbor_chunks(
        self, chunks: List[Chunk], current_idx: int, radius: int = 1
    ) -> List[Tuple[int, Chunk]]:
        """获取相邻的chunks"""
        neighbors = []
        for i in range(max(0, current_idx - radius), min(len(chunks), current_idx + radius + 1)):
            neighbors.append((i, chunks[i]))
        return neighbors
    
    def _summarize_chunk(self, chunk: Chunk, max_length: int = 200) -> str:
        """生成chunk的摘要"""
        content = chunk.content
        
        # 提取关键信息
        lines = content.split('\n')
        
        # 查找API端点
        api_pattern = r'(GET|POST|PUT|DELETE|PATCH)\s+(/[^\s]+)'
        api_matches = re.findall(api_pattern, content)
        if api_matches:
            return f"包含API端点: {', '.join([f'{m[0]} {m[1]}' for m in api_matches[:2]])}"
        
        # 查找标题
        for line in lines:
            if line.strip().startswith('#') or len(line.strip()) < 100:
                return f"章节: {line.strip()[:max_length]}"
        
        # 默认返回开头
        return content[:max_length] + "..." if len(content) > max_length else content
    
    def _estimate_tokens(self, text: str) -> int:
        """估算token数量"""
        if not text:
            return 0
        return len(text) // self.chars_per_token
