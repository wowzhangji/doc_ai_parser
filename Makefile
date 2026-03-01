.PHONY: help install test lint format clean run-api run-cli

help:
	@echo "API Doc Parser - 可用命令:"
	@echo "  make install      - 安装依赖"
	@echo "  make test         - 运行测试"
	@echo "  make lint         - 运行代码检查"
	@echo "  make format       - 格式化代码"
	@echo "  make clean        - 清理缓存文件"
	@echo "  make run-api      - 启动Web服务"
	@echo "  make run-cli      - 运行CLI帮助"

install:
	pip install -r requirements.txt
	pip install -e .

test:
	pytest -v

lint:
	ruff check src tests
	mypy src

format:
	black src tests
	ruff check --fix src tests

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +

run-api:
	uvicorn src.api:app --reload --host 0.0.0.0 --port 8000

run-cli:
	api-doc-parser --help
