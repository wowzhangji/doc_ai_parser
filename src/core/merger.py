"""结果合并器"""

from typing import Any, Dict, List, Optional, Set
import structlog

from src.models.result import ParseResult

logger = structlog.get_logger()


class ResultMerger:
    """解析结果合并器"""
    
    def __init__(self):
        self.logger = logger.bind(component="ResultMerger")
    
    def merge(self, results: List[ParseResult]) -> ParseResult:
        """
        合并多个解析结果
        
        通常用于：
        1. 合并多个chunk的解析结果
        2. 合并增量更新的结果
        """
        if not results:
            return ParseResult()
        
        if len(results) == 1:
            return results[0]
        
        # 以第一个结果为基准
        base = results[0]
        
        # 合并数据
        merged_data = base.data.copy()
        all_warnings = list(base.metadata.warnings)
        all_failed_chunks = list(base.metadata.failed_chunks)
        total_chunks = base.metadata.total_chunks
        processed_chunks = base.metadata.processed_chunks
        
        for result in results[1:]:
            # 合并数据
            merged_data = self._merge_data(merged_data, result.data)
            
            # 合并元数据
            all_warnings.extend(result.metadata.warnings)
            all_failed_chunks.extend(result.metadata.failed_chunks)
            total_chunks += result.metadata.total_chunks
            processed_chunks += result.metadata.processed_chunks
        
        # 去重
        all_warnings = list(set(all_warnings))
        all_failed_chunks = list(set(all_failed_chunks))
        
        # 计算新的置信度
        confidence = processed_chunks / total_chunks if total_chunks > 0 else 0.0
        
        # 创建合并后的结果
        from datetime import datetime
        from src.models.result import ParseMetadata
        
        merged_metadata = ParseMetadata(
            total_chunks=total_chunks,
            processed_chunks=processed_chunks,
            failed_chunks=all_failed_chunks,
            confidence_score=confidence,
            warnings=all_warnings,
            processing_time=sum(r.metadata.processing_time or 0 for r in results),
            model_used=base.metadata.model_used,
            provider_used=base.metadata.provider_used,
        )
        
        return ParseResult(
            version=base.version,
            parsed_at=datetime.now(),
            source_fingerprint=base.source_fingerprint,
            data=merged_data,
            metadata=merged_metadata,
        )
    
    def _merge_data(self, base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
        """深度合并数据字典"""
        result = base.copy()
        
        for key, value in update.items():
            if key not in result:
                result[key] = value
            elif isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_data(result[key], value)
            elif isinstance(result[key], list) and isinstance(value, list):
                result[key] = self._smart_merge_lists(result[key], value)
            else:
                # 标量值，update覆盖base
                result[key] = value
        
        return result
    
    def _smart_merge_lists(self, list1: List, list2: List) -> List:
        """智能合并两个列表"""
        if not list1:
            return list2.copy()
        if not list2:
            return list1.copy()
        
        # 检查列表元素类型
        first_item = list1[0] if list1 else None
        
        if isinstance(first_item, dict):
            # 字典列表，基于关键字段去重合并
            return self._merge_dict_lists(list1, list2)
        else:
            # 简单列表，去重合并
            combined = list1 + [item for item in list2 if item not in list1]
            return combined
    
    def _merge_dict_lists(self, list1: List[Dict], list2: List[Dict]) -> List[Dict]:
        """合并字典列表，基于关键字段去重"""
        # 确定关键字段
        key_fields = self._identify_key_fields(list1 + list2)
        
        if not key_fields:
            # 无法确定关键字段，简单合并
            return list1 + [item for item in list2 if item not in list1]
        
        # 使用关键字段去重
        seen_keys: Set[tuple] = set()
        result = []
        
        for item in list1 + list2:
            key = tuple(item.get(field) for field in key_fields if field in item)
            if key not in seen_keys:
                seen_keys.add(key)
                result.append(item)
        
        return result
    
    def _identify_key_fields(self, items: List[Dict]) -> List[str]:
        """识别字典列表的关键字段"""
        if not items:
            return []
        
        # 常见API相关关键字段
        candidates = [
            ["path", "method"],  # REST API端点
            ["name"],  # 按名称
            ["endpoint"],  # 端点URL
            ["url"],  # URL
            ["id"],  # ID
            ["key"],  # 键
        ]
        
        for candidate in candidates:
            # 检查这个字段组合是否在所有项中都存在且唯一
            if self._is_valid_key_field(items, candidate):
                return candidate
        
        return []
    
    def _is_valid_key_field(self, items: List[Dict], fields: List[str]) -> bool:
        """检查字段组合是否是有效的关键字段"""
        seen = set()
        
        for item in items:
            # 检查所有字段是否存在
            if not all(field in item for field in fields):
                return False
            
            # 检查值是否唯一
            key = tuple(item[field] for field in fields)
            if key in seen:
                return False
            seen.add(key)
        
        return True
    
    def deduplicate_endpoints(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """专门用于去重API端点"""
        result = data.copy()
        
        # 常见的端点列表字段名
        endpoint_fields = ["endpoints", "apis", "routes", "paths", "operations"]
        
        for field in endpoint_fields:
            if field in result and isinstance(result[field], list):
                result[field] = self._deduplicate_endpoint_list(result[field])
        
        return result
    
    def _deduplicate_endpoint_list(self, endpoints: List[Dict]) -> List[Dict]:
        """去重API端点列表"""
        if not endpoints:
            return endpoints
        
        seen = set()
        result = []
        
        for endpoint in endpoints:
            # 构建唯一标识
            path = endpoint.get("path", "")
            method = endpoint.get("method", "").upper()
            name = endpoint.get("name", "")
            
            # 优先使用path+method作为标识
            if path and method:
                key = f"{method}:{path}"
            elif path:
                key = path
            elif name:
                key = name
            else:
                # 无法确定唯一标识，保留
                result.append(endpoint)
                continue
            
            if key not in seen:
                seen.add(key)
                result.append(endpoint)
        
        return result
