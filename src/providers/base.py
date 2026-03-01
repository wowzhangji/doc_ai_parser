"""LLM提供商基类"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import structlog

from src.models.document import Chunk
from src.models.request import RequirementDoc

logger = structlog.get_logger()


@dataclass
class ProviderConfig:
    """提供商配置"""
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    temperature: float = 0.1
    max_retries: int = 3
    timeout: float = 60.0


class LLMProvider(ABC):
    """LLM提供商基类"""
    
    def __init__(self, config: ProviderConfig):
        self.config = config
        self.logger = logger.bind(provider=self.__class__.__name__)
    
    @abstractmethod
    async def parse(
        self, 
        chunk: Chunk, 
        requirement: RequirementDoc,
        output_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        解析文档片段
        
        Args:
            chunk: 文档分块
            requirement: 解析要求
            output_schema: 输出JSON Schema
            
        Returns:
            解析结果字典
        """
        pass
    
    @abstractmethod
    def get_default_model(self) -> str:
        """获取默认模型名称"""
        pass
    
    def build_system_prompt(self, requirement: RequirementDoc) -> str:
        """构建系统提示词"""
        base_prompt = """你是一个专业的API文档解析专家。
你的任务是根据提供的需求说明，从API文档中提取结构化信息。

规则：
1. 严格按照需求说明中的字段要求提取信息
2. 如果某字段在文档中不存在，使用null表示
3. 保持数据类型与需求说明一致
4. 注意识别API端点之间的关联关系
5. 输出必须是有效的JSON格式
6. 不要添加任何解释性文字，只输出JSON
"""
        
        if requirement.extraction_rules:
            base_prompt += "\n提取规则：\n"
            for rule in requirement.extraction_rules:
                req_mark = "[必填]" if rule.required else "[可选]"
                base_prompt += f"- {rule.field_name} {req_mark}: {rule.description}\n"
        
        return base_prompt
    
    def build_user_prompt(
        self, 
        chunk: Chunk, 
        requirement: RequirementDoc,
        output_schema: Optional[Dict[str, Any]] = None
    ) -> str:
        """构建用户提示词"""
        parts = []
        
        # 需求说明
        parts.append("【需求说明】")
        parts.append(requirement.content)
        
        # 输出格式
        if output_schema:
            parts.append("\n【输出格式要求】")
            parts.append(json.dumps(output_schema, ensure_ascii=False, indent=2))
        
        # 上下文信息
        if chunk.context:
            parts.append("\n【上下文信息】")
            parts.append(chunk.context)
        
        # 待解析内容
        parts.append("\n【待解析的API文档片段】")
        parts.append(chunk.content)
        
        parts.append("\n请根据以上信息，输出符合要求的JSON结果。")
        
        return "\n\n".join(parts)
    
    def parse_json_response(self, response: str) -> Dict[str, Any]:
        """解析JSON响应"""
        # 尝试直接解析
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # 尝试提取JSON代码块
        import re
        json_pattern = r'```(?:json)?\s*([\s\S]*?)```'
        matches = re.findall(json_pattern, response)
        
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue
        
        # 尝试找到JSON对象
        json_pattern = r'\{[\s\S]*\}'
        match = re.search(json_pattern, response)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        
        # 如果都失败，返回原始内容
        self.logger.warning("failed_to_parse_json", response_preview=response[:200])
        return {"raw_response": response, "parse_error": True}
