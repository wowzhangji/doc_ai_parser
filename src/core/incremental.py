"""增量更新模块"""

import hashlib
from typing import Any, Dict, List, Optional, Set, Tuple
import structlog

from src.models.document import Chunk, Document
from src.models.result import ParseResult, ParseMetadata
from src.core.chunker import SmartChunker

logger = structlog.get_logger()


class IncrementalParser:
    """增量解析器 - 支持文档变更的增量更新"""
    
    def __init__(self, chunker: Optional[SmartChunker] = None):
        self.chunker = chunker or SmartChunker()
        self.logger = logger.bind(component="IncrementalParser")
    
    def compute_document_fingerprint(self, document: Document) -> str:
        """计算文档指纹"""
        return hashlib.sha256(document.content.encode()).hexdigest()
    
    def compute_chunk_fingerprint(self, chunk: Chunk) -> str:
        """计算分块指纹"""
        return hashlib.sha256(chunk.content.encode()).hexdigest()[:16]
    
    def detect_changes(
        self,
        old_document: Optional[Document],
        new_document: Document,
        old_result: Optional[ParseResult]
    ) -> Tuple[List[Chunk], List[int]]:
        """
        检测文档变更
        
        Returns:
            (changed_chunks, unchanged_chunk_indices)
        """
        # 对新文档进行分块
        new_chunks = self.chunker.chunk(new_document)
        
        if old_document is None or old_result is None:
            # 没有历史数据，全部重新解析
            return new_chunks, []
        
        # 计算旧文档的chunk指纹
        old_fingerprints = self._get_old_chunk_fingerprints(old_result)
        
        changed_chunks = []
        unchanged_indices = []
        
        for i, chunk in enumerate(new_chunks):
            chunk_fp = self.compute_chunk_fingerprint(chunk)
            
            if chunk_fp in old_fingerprints:
                # 这个chunk没有变化
                unchanged_indices.append(i)
                chunk.metadata["unchanged"] = True
                chunk.metadata["old_fingerprint"] = chunk_fp
            else:
                # 这个chunk是新的或已变更
                changed_chunks.append(chunk)
                chunk.metadata["changed"] = True
        
        self.logger.info(
            "change_detection_complete",
            total_chunks=len(new_chunks),
            changed_chunks=len(changed_chunks),
            unchanged_chunks=len(unchanged_indices),
        )
        
        return changed_chunks, unchanged_indices
    
    def _get_old_chunk_fingerprints(self, old_result: ParseResult) -> Set[str]:
        """从历史结果中获取chunk指纹"""
        fingerprints = set()
        
        # 尝试从元数据中获取
        if old_result.metadata and hasattr(old_result.metadata, "chunk_fingerprints"):
            fingerprints.update(old_result.metadata.chunk_fingerprints)
        
        # 也可以从data中尝试提取
        if "_chunk_fingerprints" in old_result.data:
            fingerprints.update(old_result.data["_chunk_fingerprints"])
        
        return fingerprints
    
    def merge_incremental_results(
        self,
        old_result: ParseResult,
        new_chunks_result: ParseResult,
        unchanged_indices: List[int],
        all_chunks_count: int
    ) -> ParseResult:
        """
        合并增量解析结果
        
        保留未变更部分，使用新结果替换变更部分
        """
        # 合并数据
        merged_data = old_result.data.copy()
        
        # 更新变更的部分
        for key, value in new_chunks_result.data.items():
            if key.startswith("_"):
                continue
            merged_data[key] = value
        
        # 合并元数据
        all_warnings = list(set(
            old_result.metadata.warnings + new_chunks_result.metadata.warnings
        ))
        
        all_failed_chunks = list(set(
            old_result.metadata.failed_chunks + new_chunks_result.metadata.failed_chunks
        ))
        
        # 计算总的处理统计
        total_processed = (
            len(unchanged_indices) + new_chunks_result.metadata.processed_chunks
        )
        
        confidence = total_processed / all_chunks_count if all_chunks_count > 0 else 0.0
        
        from datetime import datetime
        
        merged_metadata = ParseMetadata(
            total_chunks=all_chunks_count,
            processed_chunks=total_processed,
            failed_chunks=all_failed_chunks,
            confidence_score=confidence,
            warnings=all_warnings,
            processing_time=(
                old_result.metadata.processing_time or 0
            ) + new_chunks_result.metadata.processing_time,
            model_used=new_chunks_result.metadata.model_used or old_result.metadata.model_used,
            provider_used=new_chunks_result.metadata.provider_used or old_result.metadata.provider_used,
        )
        
        return ParseResult(
            version=old_result.version,
            parsed_at=datetime.now(),
            source_fingerprint=new_chunks_result.source_fingerprint,
            data=merged_data,
            metadata=merged_metadata,
            is_incremental=True,
            changed_fields=list(new_chunks_result.data.keys()),
        )
    
    def create_chunk_fingerprint_map(
        self,
        chunks: List[Chunk]
    ) -> Dict[str, int]:
        """创建chunk指纹到索引的映射"""
        return {
            self.compute_chunk_fingerprint(chunk): i 
            for i, chunk in enumerate(chunks)
        }
    
    def extract_unchanged_data(
        self,
        old_result: ParseResult,
        unchanged_indices: List[int],
        chunk_map: Dict[str, int]
    ) -> Dict[str, Any]:
        """
        从历史结果中提取未变更部分的数据
        
        这是一个可选的优化，可以根据具体需求实现
        """
        # 默认返回原始数据
        # 子类可以重写此方法以实现更精细的增量提取
        return old_result.data
    
    def should_full_reparse(
        self,
        old_document: Optional[Document],
        new_document: Document,
        change_threshold: float = 0.5
    ) -> bool:
        """
        判断是否应该完全重新解析
        
        当变更比例超过阈值时，完全重新解析可能更高效
        """
        if old_document is None:
            return True
        
        old_fp = self.compute_document_fingerprint(old_document)
        new_fp = self.compute_document_fingerprint(new_document)
        
        if old_fp == new_fp:
            # 文档完全相同
            return False
        
        # 简单的变更比例估算
        # 实际应用中可以使用更复杂的diff算法
        old_len = len(old_document.content)
        new_len = len(new_document.content)
        
        if old_len == 0:
            return True
        
        size_diff_ratio = abs(new_len - old_len) / old_len
        
        return size_diff_ratio > change_threshold
