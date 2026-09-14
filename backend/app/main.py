"""FastAPI 应用入口。

启动方式（在 backend 目录下）：
    uvicorn app.main:app --reload --port 8000

启动后：
    http://127.0.0.1:8000/docs      交互式 API 文档（答辩演示用这个）
    http://127.0.0.1:8000/api/health
    http://127.0.0.1:8000/api/env-check   环境自检
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.core.config import settings
from app.core.logging import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动/关闭钩子。"""
    setup_logging()
    logger.info("=" * 62)
    logger.info("%s 启动中", settings.app_name)
    logger.info("环境: %s | 端口: 8000", settings.env)
    logger.info("LLM 配置: %s", "已配置" if settings.llm_configured else "未配置 ← 需填 .env")
    logger.info("多模态: %s", "已启用" if settings.multimodal_enabled else "未启用（视频将降级）")

    # 确保存储目录存在，否则 SQLite / 文件输出会报路径错误
    Path(settings.storage_dir).mkdir(parents=True, exist_ok=True)

    if not settings.llm_configured:
        logger.warning("未检测到 LLM_API_KEY：/profile/chat 与 /resources/generate 会返回 503")
        logger.warning("解决：复制 backend/.env.example 为 backend/.env 并填入 Key")

    logger.info("=" * 62)
    yield
    logger.info("%s 已关闭", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    description="基于多智能体的个性化学习资源生成系统",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS：前端跑在 5173，后端 8000，属于跨域，必须显式放行
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/", summary="根路径")
async def root() -> dict[str, str]:
    return {
        "app": settings.app_name,
        "docs": "/docs",
        "health": f"{settings.api_prefix}/health",
    }
