.PHONY: help install test lint format typecheck clean run docker

help: ## 显示帮助
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## 安装依赖
	uv sync

test: ## 运行测试
	uv run pytest tests/ -v

lint: ## 代码检查
	uv run ruff check src/ tests/

format: ## 代码格式化
	uv run ruff format src/ tests/

typecheck: ## 类型检查
	uv run mypy src/dingding_service/

all: lint typecheck test ## 全部检查

run: ## 启动服务
	uv run dingding-spreadsheet

docker: ## 构建 Docker 镜像
	docker compose build
