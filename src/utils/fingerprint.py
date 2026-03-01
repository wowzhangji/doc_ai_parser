"""指纹计算工具"""

import hashlib
from typing import Optional

from src.models.document import Chunk


def compute_fingerprint(content: str, algorithm: str = "sha256") -> str:
    """
    计算内容指纹
    
    Args:
        content: 内容字符串
        algorithm: 哈希算法 (sha256, md5, sha1)
        
    Returns:
        指纹字符串（前16位）
    """
    if algorithm == "sha256":
        hasher = hashlib.sha256()
    elif algorithm == "md5":
        hasher = hashlib.md5()
    elif algorithm == "sha1":
        hasher = hashlib.sha1()
    else:
        raise ValueError(f"不支持的哈希算法: {algorithm}")
    
    hasher.update(content.encode('utf-8'))
    return hasher.hexdigest()[:16]


def compute_chunk_fingerprint(chunk: Chunk, include_context: bool = False) -> str:
    """
    计算分块指纹
    
    Args:
        chunk: 文档分块
        include_context: 是否包含上下文信息
        
    Returns:
        指纹字符串
    """
    content = chunk.content
    if include_context and chunk.context:
        content = chunk.context + "\n" + content
    
    return compute_fingerprint(content)


def compute_file_fingerprint(file_path: str) -> str:
    """
    计算文件指纹
    
    Args:
        file_path: 文件路径
        
    Returns:
        指纹字符串
    """
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            hasher.update(chunk)
    return hasher.hexdigest()[:16]


def compare_fingerprints(fp1: str, fp2: str) -> bool:
    """
    比较两个指纹是否相同
    
    Args:
        fp1: 指纹1
        fp2: 指纹2
        
    Returns:
        是否相同
    """
    return fp1 == fp2
