# API Doc Parser

使用大模型智能解析API文档的工具，支持PDF、Word、Excel等多种格式，可输出结构化的JSON数据。

## 功能特性

- **多格式支持**: PDF、Word (docx)、Excel (xlsx)、纯文本
- **智能分块**: 结构感知分块 + 滑动窗口，保证信息不丢失
- **多LLM支持**: OpenAI、Azure OpenAI、Anthropic Claude、Ollama本地模型
- **自定义API**: 支持自定义OpenAI和Anthropic协议API（vLLM、TGI等）
- **增量更新**: 支持文档变更的增量解析
- **多种使用方式**: CLI命令行 + FastAPI Web服务

## 快速开始

### 安装

```bash
# 克隆仓库
git clone <repository-url>
cd doc_ai_parser

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或 .venv\Scripts\activate  # Windows

# 安装依赖
pip install -e ".[dev]"
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
├── pyproject.toml
└── README.md
```

## 开发

```bash
# 运行测试
pytest

# 代码格式化
black src tests
ruff check src tests

# 类型检查
mypy src
```

## License

MIT License
