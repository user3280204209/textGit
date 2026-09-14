# ============================================================
# 常用命令统一入口
# ============================================================
# Windows 下 make 不一定可用（Git Bash 自带）。
# 优先用 scripts/setup.ps1 与 scripts/dev.ps1；
# 本文件是给 Mac / Linux 组员和 CI 用的等价入口。
# ============================================================

ENV_NAME ?= learnagent
BACKEND_PORT ?= 8000

.PHONY: help setup backend-deps env dev backend frontend test lint format clean

help:
	@echo "可用命令："
	@echo "  make setup        - 一键初始化（环境 + 依赖 + .env）"
	@echo "  make env          - 只创建 conda 环境"
	@echo "  make backend-deps - 只安装后端依赖"
	@echo "  make dev          - 同时启动前后端"
	@echo "  make backend      - 只启动后端"
	@echo "  make frontend     - 只启动前端"
	@echo "  make test         - 跑后端测试"
	@echo "  make lint         - 代码检查（Python + 前端）"
	@echo "  make format       - 自动格式化"
	@echo "  make clean        - 清理缓存与产物"

setup:
	pwsh -File scripts/setup.ps1 || sh scripts/setup.sh

env:
	conda create -n $(ENV_NAME) python=3.13 -y

backend-deps:
	conda run -n $(ENV_NAME) python -m pip install -r backend/requirements.txt

dev:
	pwsh -File scripts/dev.ps1

backend:
	cd backend && conda run -n $(ENV_NAME) uvicorn app.main:app --reload --port $(BACKEND_PORT)

frontend:
	cd frontend && pnpm dev

test:
	cd backend && conda run -n $(ENV_NAME) pytest

lint:
	cd backend && conda run -n $(ENV_NAME) ruff check .
	cd frontend && pnpm lint

format:
	cd backend && conda run -n $(ENV_NAME) ruff format .
	cd frontend && pnpm format

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -prune -exec rm -rf {} +
	find . -type d -name .ruff_cache -prune -exec rm -rf {} +
	rm -rf frontend/dist backend/storage
