"""LLM解析引擎"""

import asyncio
import hashlib
import time
from typing import Any, Dict, List, Optional

import structlog

from src.models.document import Chunk, Document
from src.models.request import ParseConfig, ParseRequest, RequirementDoc
from src.models.result import ParseResult, ParseMetadata
from src.core.chunker import SmartChunker
from src.providers.factory import get_provider
from src.providers.base import LLMProvider

logger = structlog.get_logger()


class LLMParser:
    """LLM文档解析引擎"""
    
    def __init__(self, config: Optional[ParseConfig] = None):
        self.config = config or ParseConfig()
        self.chunker = SmartChunker(
            max_tokens=self.config.chunk_size,
            overlap_tokens=self.config.chunk_overlap
        )
        self._provider: Optional[LLMProvider] = None
        self._cache: Dict[str, Any] = {}  # 简单的内存缓存
    
    @property
    def provider(self) -> LLMProvider:
        """获取或创建LLM提供商"""
        if self._provider is None:
            self._provider = get_provider(
                provider_name=self.config.provider,
                api_key=self.config.api_key,
                api_base=self.config.api_base,
                model=self.config.model,
                temperature=self.config.temperature,
                max_retries=self.config.max_retries,
            )
        return self._provider
    
    async def parse(
        self,
        request: ParseRequest,
        progress_callback: Optional[callable] = None
    ) -> ParseResult:
        """
        解析文档
        
        Args:
            request: 解析请求
            progress_callback: 进度回调函数，接收(current, total)参数
            
        Returns:
            解析结果
        """
        start_time = time.time()
        
        # 1. 加载文档
        from src.core.loader import get_loader
        loader = get_loader(request.source_document.file_type)
        
        if request.source_document.file_path:
            document = loader.load(request.source_document.file_path)
        else:
            document = loader.load(request.source_document.file_content)
        
        logger.info(
            "document_loaded",
            file_type=request.source_document.file_type,
            content_length=len(document.content),
        )
        
        # 2. 计算文档指纹
        source_fingerprint = self._compute_fingerprint(document.content)
        
        # 3. 分块
        chunks = self.chunker.chunk(document)
        logger.info("document_chunked", chunk_count=len(chunks))
        
        # 4. 并发解析各个块
        chunk_results = await self._parse_chunks(
            chunks,
            request.requirement_doc,
            request.requirement_doc.output_schema,
            progress_callback
        )
        
        # 5. 合并结果
        merged_data = self._merge_chunk_results(chunk_results)
        
        # 6. 构建最终结果
        processing_time = time.time() - start_time
        
        failed_chunks = [
            i for i, result in enumerate(chunk_results) 
            if result.get("_parse_error")
        ]
        
        metadata = ParseMetadata(
            total_chunks=len(chunks),
            processed_chunks=len(chunks) - len(failed_chunks),
            failed_chunks=failed_chunks,
            confidence_score=self._calculate_confidence(chunk_results),
            warnings=self._collect_warnings(chunk_results),
            processing_time=processing_time,
            model_used=self.config.model or self.provider.get_default_model(),
            provider_used=self.config.provider,
        )
        
        result = ParseResult(
            source_fingerprint=source_fingerprint,
            data=merged_data,
            metadata=metadata,
        )
        
        logger.info(
            "parse_completed",
            processing_time=processing_time,
            total_chunks=len(chunks),
            failed_chunks=len(failed_chunks),
        )
        
        return result
    
    async def _parse_chunks(
        self,
        chunks: List[Chunk],
        requirement: RequirementDoc,
        output_schema: Optional[Dict[str, Any]],
        progress_callback: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """并发解析所有chunks"""
        semaphore = asyncio.Semaphore(5)  # 限制并发数
        
        async def parse_with_limit(chunk: Chunk, index: int) -> Dict[str, Any]:
            async with semaphore:
                result = await self._parse_single_chunk(
                    chunk, requirement, output_schema
                )
                if progress_callback:
                    progress_callback(index + 1, len(chunks))
                return result
        
        tasks = [
            parse_with_limit(chunk, i) 
            for i, chunk in enumerate(chunks)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error("chunk_parse_failed", chunk_index=i, error=str(result))
                processed_results.append({
                    "_parse_error": True,
                    "_error_message": str(result),
                    "_chunk_index": i,
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _parse_single_chunk(
        self,
        chunk: Chunk,
        requirement: RequirementDoc,
        output_schema: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """解析单个chunk"""
        # 检查缓存
        if self.config.use_cache:
            cache_key = self._compute_cache_key(chunk, requirement)
            if cache_key in self._cache:
                logger.debug("cache_hit", chunk_index=chunk.index)
                return self._cache[cache_key]
        
        try:
            result = await self.provider.parse(chunk, requirement, output_schema)
            
            # 存入缓存
            if self.config.use_cache:
                self._cache[cache_key] = result
            
            return result
            
        except Exception as e:
            logger.error("parse_chunk_error", chunk_index=chunk.index, error=str(e))
            return {
                "_parse_error": True,
                "_error_message": str(e),
                "_chunk_index": chunk.index,
            }
    
    def _merge_chunk_results(self, chunk_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """合并所有chunk的解析结果"""
        merged = {}
        
        for result in chunk_results:
            if result.get("_parse_error"):
                continue
            
            # 递归合并字典
            merged = self._deep_merge(merged, result)
        
        return merged
    
    def _deep_merge(self, base: Dict, update: Dict) -> Dict:
        """深度合并两个字典"""
        result = base.copy()
        
        for key, value in update.items():
            # 跳过内部字段
            if key.startswith("_"):
                continue
                
            if key in result:
                if isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = self._deep_merge(result[key], value)
                elif isinstance(result[key], list) and isinstance(value, list):
                    # 合并列表，去重
                    result[key] = self._merge_lists(result[key], value)
                else:
                    # 非容器类型，新值覆盖旧值
                    result[key] = value
            else:
                result[key] = value
        
        return result
    
    def _merge_lists(self, list1: List, list2: List) -> List:
        """合并两个列表，基于某些字段去重"""
        result = list1.copy()
        
        for item in list2:
            # 如果是字典列表，尝试基于某些关键字段去重
            if isinstance(item, dict):
                # 尝试用path或name字段去重
                key_fields = ["path", "name", "endpoint", "url", "id"]
                key_field = None
                for field in key_fields:
                    if field in item:
                        key_field = field
                        break
                
                if key_field:
                    item_key = item.get(key_field)
                    exists = any(
                        isinstance(existing, dict) and existing.get(key_field) == item_key
                        for existing in result
                    )
                    if not exists:
                        result.append(item)
                else:
                    # 无法确定关键字段，直接添加
                    if item not in result:
                        result.append(item)
            else:
                if item not in result:
                    result.append(item)
        
        return result
    
    def _calculate_confidence(self, chunk_results: List[Dict[str, Any]]) -> float:
        """计算整体置信度"""
        if not chunk_results:
            return 0.0
        
        successful = sum(1 for r in chunk_results if not r.get("_parse_error"))
        return successful / len(chunk_results)
    
    def _collect_warnings(self, chunk_results: List[Dict[str, Any]]) -> List[str]:
        """收集所有警告信息"""
        warnings = []
        
        for i, result in enumerate(chunk_results):
            if result.get("_parse_error"):
                warnings.append(f"Chunk {i} 解析失败: {result.get('_error_message', '未知错误')}")
            
            if "warnings" in result:
                chunk_warnings = result["warnings"]
                if isinstance(chunk_warnings, list):
                    warnings.extend([f"Chunk {i}: {w}" for w in chunk_warnings])
                elif isinstance(chunk_warnings, str):
                    warnings.append(f"Chunk {i}: {chunk_warnings}")
        
        return warnings
    
    def _compute_fingerprint(self, content: str) -> str:
        """计算内容指纹"""
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _compute_cache_key(self, chunk: Chunk, requirement: RequirementDoc) -> str:
        """计算缓存键"""
        key_data = f"{chunk.content}:{requirement.content}:{self.config.model}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]
