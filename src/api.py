"""FastAPI Web服务"""

import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.models.request import (
    ParseRequest,
    ParseConfig,
    DocumentSource,
    RequirementDoc,
)
from src.models.result import ParseResult
from src.core.parser import LLMParser
from src.config import settings

# 创建FastAPI应用
app = FastAPI(
    title="API Doc Parser",
    description="使用大模型解析API文档的智能工具",
    version="0.1.0",
)

# 内存中的任务存储（生产环境应使用Redis等）
tasks: Dict[str, dict] = {}


class ParseTaskResponse(BaseModel):
    """解析任务响应"""
    task_id: str
    status: str
    message: str


class TaskStatus(BaseModel):
    """任务状态"""
    task_id: str
    status: str  # pending, processing, completed, failed
    created_at: str
    updated_at: Optional[str] = None
    progress: Optional[dict] = None
    result: Optional[dict] = None
    error: Optional[str] = None


class ParseRequestBody(BaseModel):
    """解析请求体"""
    requirement_content: str
    output_schema: Optional[dict] = None
    extraction_rules: Optional[list] = None
    config: Optional[dict] = None


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "API Doc Parser",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


@app.post("/parse", response_model=ParseTaskResponse)
async def create_parse_task(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="API文档文件 (PDF/Word/Excel)"),
    requirement_content: str = Form(..., description="解析要求说明"),
    output_schema: Optional[str] = Form(None, description="输出JSON Schema (JSON字符串)"),
    provider: str = Form("openai", description="LLM提供商"),
    model: Optional[str] = Form(None, description="模型名称"),
    api_base: Optional[str] = Form(None, description="自定义API基础URL"),
    api_key: Optional[str] = Form(None, description="API密钥"),
    chunk_size: int = Form(3000, description="分块大小"),
    temperature: float = Form(0.1, description="温度参数"),
):
    """
    创建解析任务
    
    上传API文档文件并指定解析要求，系统将异步处理并返回任务ID
    """
    # 生成任务ID
    task_id = str(uuid.uuid4())
    
    # 检测文件类型
    file_type = _detect_file_type(file.filename)
    if not file_type:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {file.filename}"
        )
    
    # 读取文件内容
    file_content = await file.read()
    
    if len(file_content) > settings.max_file_size:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大，最大支持 {settings.max_file_size / 1024 / 1024}MB"
        )
    
    # 解析output_schema
    parsed_schema = {}
    if output_schema:
        try:
            parsed_schema = json.loads(output_schema)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail="output_schema 必须是有效的JSON字符串"
            )
    
    # 创建任务
    tasks[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "updated_at": None,
        "progress": None,
        "result": None,
        "error": None,
        "file_content": file_content,
        "file_type": file_type,
        "requirement_content": requirement_content,
        "output_schema": parsed_schema,
        "config": {
            "provider": provider,
            "model": model,
            "api_base": api_base,
            "api_key": api_key,
            "chunk_size": chunk_size,
            "temperature": temperature,
        }
    }
    
    # 启动后台任务
    background_tasks.add_task(_process_parse_task, task_id)
    
    return ParseTaskResponse(
        task_id=task_id,
        status="pending",
        message="解析任务已创建，请使用任务ID查询状态"
    )


@app.get("/parse/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """获取任务状态"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task = tasks[task_id]
    
    return TaskStatus(
        task_id=task_id,
        status=task["status"],
        created_at=task["created_at"],
        updated_at=task["updated_at"],
        progress=task["progress"],
        result=task["result"],
        error=task["error"],
    )


@app.post("/parse/sync")
async def parse_sync(
    file: UploadFile = File(..., description="API文档文件"),
    requirement_content: str = Form(..., description="解析要求说明"),
    output_schema: Optional[str] = Form(None, description="输出JSON Schema"),
    provider: str = Form("openai", description="LLM提供商"),
    model: Optional[str] = Form(None, description="模型名称"),
    api_base: Optional[str] = Form(None, description="自定义API基础URL"),
    api_key: Optional[str] = Form(None, description="API密钥"),
    chunk_size: int = Form(3000, description="分块大小"),
    temperature: float = Form(0.1, description="温度参数"),
):
    """
    同步解析（适用于小文档）
    
    直接返回解析结果，不通过任务队列
    """
    # 检测文件类型
    file_type = _detect_file_type(file.filename)
    if not file_type:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {file.filename}"
        )
    
    # 读取文件内容
    file_content = await file.read()
    
    if len(file_content) > settings.max_file_size:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大，最大支持 {settings.max_file_size / 1024 / 1024}MB"
        )
    
    # 解析output_schema
    parsed_schema = {}
    if output_schema:
        try:
            parsed_schema = json.loads(output_schema)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail="output_schema 必须是有效的JSON字符串"
            )
    
    # 构建请求
    extraction_rules = []
    requirement_doc = RequirementDoc(
        content=requirement_content,
        output_schema=parsed_schema,
        extraction_rules=extraction_rules,
    )
    
    config = ParseConfig(
        provider=provider,
        model=model,
        api_base=api_base,
        api_key=api_key,
        chunk_size=chunk_size,
        temperature=temperature,
    )
    
    request = ParseRequest(
        source_document=DocumentSource(
            file_content=file_content,
            file_type=file_type,
        ),
        requirement_doc=requirement_doc,
        config=config,
    )
    
    # 执行解析
    try:
        parser = LLMParser(config)
        result = await parser.parse(request)
        return result.dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/providers")
async def list_providers():
    """列出支持的LLM提供商"""
    return {
        "providers": [
            {
                "name": "openai",
                "description": "OpenAI官方API",
                "requires_api_key": True,
                "requires_api_base": False,
            },
            {
                "name": "azure",
                "description": "Azure OpenAI",
                "requires_api_key": True,
                "requires_api_base": True,
            },
            {
                "name": "anthropic",
                "description": "Anthropic Claude",
                "requires_api_key": True,
                "requires_api_base": False,
            },
            {
                "name": "custom_openai",
                "description": "自定义OpenAI协议API (vLLM, TGI等)",
                "requires_api_key": False,
                "requires_api_base": True,
            },
            {
                "name": "custom_anthropic",
                "description": "自定义Anthropic协议API",
                "requires_api_key": False,
                "requires_api_base": True,
            },
            {
                "name": "ollama",
                "description": "Ollama本地模型",
                "requires_api_key": False,
                "requires_api_base": False,
            },
        ]
    }


async def _process_parse_task(task_id: str):
    """处理解析任务"""
    task = tasks[task_id]
    task["status"] = "processing"
    task["updated_at"] = datetime.now().isoformat()
    
    try:
        # 构建请求
        extraction_rules = []
        requirement_doc = RequirementDoc(
            content=task["requirement_content"],
            output_schema=task["output_schema"],
            extraction_rules=extraction_rules,
        )
        
        config = ParseConfig(**task["config"])
        
        request = ParseRequest(
            source_document=DocumentSource(
                file_content=task["file_content"],
                file_type=task["file_type"],
            ),
            requirement_doc=requirement_doc,
            config=config,
        )
        
        # 更新进度
        def progress_callback(current: int, total: int):
            task["progress"] = {
                "current": current,
                "total": total,
                "percentage": round(current / total * 100, 1) if total > 0 else 0
            }
            task["updated_at"] = datetime.now().isoformat()
        
        # 执行解析
        parser = LLMParser(config)
        result = await parser.parse(request, progress_callback)
        
        # 更新任务状态
        task["status"] = "completed"
        task["result"] = result.dict()
        task["updated_at"] = datetime.now().isoformat()
        
        # 清理文件内容以节省内存
        del task["file_content"]
        
    except Exception as e:
        task["status"] = "failed"
        task["error"] = str(e)
        task["updated_at"] = datetime.now().isoformat()


def _detect_file_type(filename: str) -> Optional[str]:
    """检测文件类型"""
    suffix = Path(filename).suffix.lower()
    type_map = {
        '.pdf': 'pdf',
        '.docx': 'docx',
        '.xlsx': 'xlsx',
        '.txt': 'txt',
        '.md': 'md',
    }
    return type_map.get(suffix)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
