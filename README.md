# API Doc Parser

使用大模型智能解析API文档的工具，支持PDF、Word、Excel等多种格式，可输出结构化的JSON数据。

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 功能特性

- **多格式支持**: PDF、Word (docx)、Excel (xlsx)、纯文本
- **智能分块**: 结构感知分块 + 滑动窗口，保证信息不丢失
- **多LLM支持**: OpenAI、Azure OpenAI、Anthropic Claude、Ollama本地模型
- **自定义API**: 支持自定义OpenAI和Anthropic协议API（vLLM、TGI等）
- **增量更新**: 支持文档变更的增量解析
- **多种使用方式**: CLI命令行 + FastAPI Web服务

## 系统要求

- Python >= 3.11
- 支持的操作系统: macOS, Linux, Windows

## 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/wowzhangji/doc_ai_parser.git
cd doc_ai_parser

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或 .venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
pip install -e .
```

或使用 Makefile:

```bash
make install
```

### 配置环境变量

创建 `.env` 文件：

```bash
# OpenAI
OPENAI_API_KEY=your-openai-api-key

# Anthropic
ANTHROPIC_API_KEY=your-anthropic-api-key

# Azure OpenAI (可选)
AZURE_OPENAI_API_KEY=your-azure-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com

# Ollama (可选)
OLLAMA_BASE_URL=http://localhost:11434
```

### CLI使用

```bash
# 生成示例要求说明文件
api-doc-parser example-requirement -o requirement.json

# 解析API文档
api-doc-parser parse \
  api_document.pdf \
  --requirement requirement.json \
  --output result.json \
  --provider openai \
  --model gpt-4

# 使用自定义API（如vLLM）
api-doc-parser parse \
  api_document.pdf \
  --requirement requirement.json \
  --output result.json \
  --provider custom_openai \
  --api-base http://localhost:8000/v1 \
  --model my-model

# 查看支持的提供商
api-doc-parser providers
```

### Web服务使用

```bash
# 启动服务
uvicorn src.api:app --reload

# 或使用 Makefile
make run-api

# 访问API文档
open http://localhost:8000/docs
```

API端点：

- `POST /parse` - 创建异步解析任务
- `GET /parse/{task_id}` - 查询任务状态
- `POST /parse/sync` - 同步解析（小文档）
- `GET /providers` - 列出支持的LLM提供商

## 要求说明文件格式

```json
{
  "content": "从API文档中提取所有API端点信息...",
  "output_schema": {
    "type": "object",
    "properties": {
      "endpoints": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "path": {"type": "string"},
            "method": {"type": "string"}
          }
        }
      }
    }
  },
  "extraction_rules": [
    {
      "field_name": "endpoints",
      "description": "所有API端点列表",
      "required": true
    }
  ]
}
```

## 支持的LLM提供商

| 提供商 | 说明 | 需要API Key | 需要API Base |
|--------|------|------------|--------------|
| openai | OpenAI官方API | 是 | 否 |
| azure | Azure OpenAI | 是 | 是 |
| anthropic | Anthropic Claude | 是 | 否 |
| custom_openai | 自定义OpenAI协议 | 可选 | 是 |
| custom_anthropic | 自定义Anthropic协议 | 可选 | 是 |
| ollama | Ollama本地模型 | 否 | 可选 |

## 项目结构

```
doc_ai_parser/
├── src/                    # Python包
│   ├── __init__.py
│   ├── cli.py              # CLI入口
│   ├── api.py              # FastAPI服务
│   ├── config.py           # 配置管理
│   ├── core/               # 核心模块
│   │   ├── loader.py       # 文档加载器
│   │   ├── chunker.py      # 智能分块器
│   │   ├── parser.py       # LLM解析引擎
│   │   ├── merger.py       # 结果合并器
│   │   └── incremental.py  # 增量更新
│   ├── models/             # 数据模型
│   ├── providers/          # LLM提供商
│   └── utils/              # 工具函数
├── tests/                  # 测试
├── requirements.txt        # 依赖文件
├── Makefile               # 常用命令
├── pyproject.toml
└── README.md
```

## 开发

```bash
# 查看所有可用命令
make help

# 运行测试
make test

# 代码格式化
make format

# 代码检查
make lint

# 清理缓存
make clean
```

## 依赖说明

- `requirements.txt` - 项目依赖（包含运行和开发工具）
- `pyproject.toml` - 项目元数据和构建配置

## License

MIT License
