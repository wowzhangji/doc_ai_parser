"""CLI入口"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.panel import Panel
from rich import box

from src.models.request import (
    ParseRequest,
    ParseConfig,
    DocumentSource,
    RequirementDoc,
)
from src.models.result import ParseResult
from src.core.parser import LLMParser

app = typer.Typer(
    name="api-doc-parser",
    help="使用大模型解析API文档的智能工具",
    no_args_is_help=True,
)
console = Console()


def version_callback(value: bool):
    """版本信息回调"""
    if value:
        console.print("[bold blue]API Doc Parser[/bold blue] version 0.1.0")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True
    ),
):
    """API文档解析工具"""
    pass


@app.command()
def parse(
    source: Path = typer.Argument(
        ..., 
        help="API文档路径 (PDF/Word/Excel)",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
    requirement: Path = typer.Option(
        ...,
        "--requirement", "-r",
        help="解析要求说明文件路径 (JSON)",
        exists=True,
    ),
    output: Path = typer.Option(
        ...,
        "--output", "-o",
        help="输出文件路径",
    ),
    provider: str = typer.Option(
        "openai",
        "--provider", "-p",
        help="LLM提供商",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model", "-m",
        help="模型名称",
    ),
    api_base: Optional[str] = typer.Option(
        None,
        "--api-base",
        help="自定义API基础URL",
    ),
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        help="API密钥",
    ),
    chunk_size: int = typer.Option(
        3000,
        "--chunk-size",
        help="分块大小（token数）",
    ),
    temperature: float = typer.Option(
        0.1,
        "--temperature", "-t",
        help="模型温度参数",
    ),
    previous_result: Optional[Path] = typer.Option(
        None,
        "--previous-result",
        help="之前的解析结果（用于增量更新）",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="显示详细输出",
    ),
):
    """解析API文档"""
    asyncio.run(_parse_async(
        source=source,
        requirement=requirement,
        output=output,
        provider=provider,
        model=model,
        api_base=api_base,
        api_key=api_key,
        chunk_size=chunk_size,
        temperature=temperature,
        previous_result=previous_result,
        verbose=verbose,
    ))


async def _parse_async(
    source: Path,
    requirement: Path,
    output: Path,
    provider: str,
    model: Optional[str],
    api_base: Optional[str],
    api_key: Optional[str],
    chunk_size: int,
    temperature: float,
    previous_result: Optional[Path],
    verbose: bool,
):
    """异步解析"""
    # 检测文件类型
    file_type = _detect_file_type(source)
    if not file_type:
        console.print(f"[red]错误: 不支持的文件类型: {source.suffix}[/red]")
        sys.exit(1)
    
    # 加载要求说明
    try:
        with open(requirement, 'r', encoding='utf-8') as f:
            req_data = json.load(f)
    except Exception as e:
        console.print(f"[red]错误: 无法加载要求说明文件: {e}[/red]")
        sys.exit(1)
    
    # 构建请求
    requirement_doc = RequirementDoc(
        content=req_data.get("content", ""),
        output_schema=req_data.get("output_schema", {}),
        extraction_rules=req_data.get("extraction_rules", []),
    )
    
    config = ParseConfig(
        provider=provider,
        model=model,
        api_base=api_base,
        api_key=api_key,
        chunk_size=chunk_size,
        temperature=temperature,
    )
    
    # 加载之前的结果（如果存在）
    prev_result = None
    if previous_result and previous_result.exists():
        try:
            with open(previous_result, 'r', encoding='utf-8') as f:
                prev_data = json.load(f)
            prev_result = ParseResult(**prev_data)
            console.print("[blue]已加载之前的解析结果，将执行增量更新[/blue]")
        except Exception as e:
            console.print(f"[yellow]警告: 无法加载之前的结果: {e}[/yellow]")
    
    request = ParseRequest(
        source_document=DocumentSource(
            file_path=source,
            file_type=file_type,
        ),
        requirement_doc=requirement_doc,
        config=config,
        previous_result=prev_result.dict() if prev_result else None,
    )
    
    # 显示配置信息
    if verbose:
        _show_config(config, source, requirement)
    
    # 执行解析
    console.print(f"\n[bold]开始解析文档:[/bold] {source.name}")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("正在解析...", total=None)
        
        parser = LLMParser(config)
        
        def progress_callback(current: int, total: int):
            progress.update(task, description=f"正在解析... {current}/{total} chunks")
        
        try:
            result = await parser.parse(request, progress_callback)
        except Exception as e:
            console.print(f"\n[red]解析失败: {e}[/red]")
            if verbose:
                import traceback
                console.print(traceback.format_exc())
            sys.exit(1)
    
    # 保存结果
    try:
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(result.dict(), f, ensure_ascii=False, indent=2)
        console.print(f"\n[green]解析完成! 结果已保存到: {output}[/green]")
    except Exception as e:
        console.print(f"\n[red]保存结果失败: {e}[/red]")
        sys.exit(1)
    
    # 显示统计信息
    _show_statistics(result)


def _detect_file_type(file_path: Path) -> Optional[str]:
    """检测文件类型"""
    suffix = file_path.suffix.lower()
    type_map = {
        '.pdf': 'pdf',
        '.docx': 'docx',
        '.xlsx': 'xlsx',
        '.txt': 'txt',
        '.md': 'md',
    }
    return type_map.get(suffix)


def _show_config(config: ParseConfig, source: Path, requirement: Path):
    """显示配置信息"""
    table = Table(title="解析配置", box=box.ROUNDED)
    table.add_column("配置项", style="cyan")
    table.add_column("值", style="green")
    
    table.add_row("文档路径", str(source))
    table.add_row("要求说明", str(requirement))
    table.add_row("提供商", config.provider)
    table.add_row("模型", config.model or "默认")
    table.add_row("分块大小", str(config.chunk_size))
    table.add_row("温度", str(config.temperature))
    
    if config.api_base:
        table.add_row("API基础URL", config.api_base)
    
    console.print(table)
    console.print()


def _show_statistics(result: ParseResult):
    """显示统计信息"""
    console.print()
    
    stats = [
        f"总Chunks: {result.metadata.total_chunks}",
        f"成功处理: {result.metadata.processed_chunks}",
        f"失败: {len(result.metadata.failed_chunks)}",
        f"置信度: {result.metadata.confidence_score:.1%}",
    ]
    
    if result.metadata.processing_time:
        stats.append(f"处理时间: {result.metadata.processing_time:.2f}s")
    
    if result.metadata.model_used:
        stats.append(f"使用模型: {result.metadata.model_used}")
    
    panel_content = "\n".join(f"• {stat}" for stat in stats)
    
    if result.metadata.warnings:
        panel_content += "\n\n[yellow]警告:[/yellow]\n"
        panel_content += "\n".join(f"  ⚠ {w}" for w in result.metadata.warnings[:5])
        if len(result.metadata.warnings) > 5:
            panel_content += f"\n  ... 还有 {len(result.metadata.warnings) - 5} 个警告"
    
    console.print(Panel(
        panel_content,
        title="解析统计",
        border_style="blue",
        box=box.ROUNDED,
    ))


@app.command()
def providers():
    """列出支持的LLM提供商"""
    table = Table(title="支持的LLM提供商", box=box.ROUNDED)
    table.add_column("提供商", style="cyan")
    table.add_column("说明", style="green")
    table.add_column("需要API Key", style="yellow")
    table.add_column("需要API Base", style="yellow")
    
    providers_info = [
        ("openai", "OpenAI官方API", "是", "否"),
        ("azure", "Azure OpenAI", "是", "是（Endpoint）"),
        ("anthropic", "Anthropic Claude", "是", "否"),
        ("custom_openai", "自定义OpenAI协议API", "可选", "是"),
        ("custom_anthropic", "自定义Anthropic协议API", "可选", "是"),
        ("ollama", "Ollama本地模型", "否", "可选"),
    ]
    
    for name, desc, api_key, api_base in providers_info:
        table.add_row(name, desc, api_key, api_base)
    
    console.print(table)
    console.print()
    console.print("[dim]提示: 使用 --api-base 指定自定义API端点，--api-key 指定API密钥[/dim]")


@app.command()
def example_requirement(
    output: Path = typer.Option(
        "requirement_example.json",
        "--output", "-o",
        help="输出文件路径",
    ),
):
    """生成示例要求说明文件"""
    example = {
        "content": "从API文档中提取所有API端点信息，包括：\n1. API路径和HTTP方法\n2. 请求参数（名称、类型、是否必填、描述）\n3. 响应数据结构\n4. 认证方式\n5. 错误码说明",
        "output_schema": {
            "type": "object",
            "properties": {
                "api_base_url": {
                    "type": "string",
                    "description": "API基础URL"
                },
                "endpoints": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "method": {"type": "string"},
                            "summary": {"type": "string"},
                            "parameters": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "type": {"type": "string"},
                                        "required": {"type": "boolean"},
                                        "description": {"type": "string"}
                                    }
                                }
                            },
                            "responses": {"type": "object"}
                        }
                    }
                }
            }
        },
        "extraction_rules": [
            {
                "field_name": "api_base_url",
                "description": "API的基础URL，如 https://api.example.com/v1",
                "required": False,
                "data_type": "string"
            },
            {
                "field_name": "endpoints",
                "description": "所有API端点列表",
                "required": True,
                "data_type": "array"
            }
        ]
    }
    
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(example, f, ensure_ascii=False, indent=2)
    
    console.print(f"[green]示例要求说明文件已生成: {output}[/green]")


if __name__ == "__main__":
    app()
