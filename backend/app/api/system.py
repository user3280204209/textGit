"""健康检查与元信息接口。

用途：
1. 前端启动时探测后端是否就绪；
2. 组员自检"我的环境到底配好了没" —— 直接看 llm_configured；
3. 答辩时展示系统依赖状态。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.core.schemas import HealthResponse
from app.store import store

router = APIRouter(tags=["系统"])


@router.get("/health", response_model=HealthResponse, summary="健康检查")
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        env=settings.env,
        llm_configured=settings.llm_configured,
        multimodal_enabled=settings.multimodal_enabled,
    )


@router.get("/env-check", summary="环境自检（给组员排查用）")
async def env_check() -> dict:
    """逐项报告依赖与配置状态，替代"跑不起来但不知道为什么"。

    这是脚手架对小白组员最实用的一个接口。
    """
    checks: list[dict[str, str | bool]] = []

    # 配置项
    checks.append(
        {
            "item": "LLM API Key",
            "ok": settings.llm_configured,
            "hint": "在 backend/.env 填 LLM_API_KEY",
        }
    )
    checks.append(
        {
            "item": "多模态 API Key（可选）",
            "ok": settings.multimodal_enabled,
            "hint": "未配置时视频资源自动降级为脚本+动画方案",
        }
    )

    # 关键依赖是否可导入
    for module_name, purpose in (
        ("fastapi", "Web 框架"),
        ("langgraph", "多智能体编排"),
        ("langchain_openai", "LLM 接入"),
        ("sqlalchemy", "数据库"),
        ("docx", "Word 文档生成"),
        ("pptx", "PPT 生成"),
    ):
        try:
            __import__(module_name)
            ok = True
        except ImportError:
            ok = False
        checks.append(
            {
                "item": f"依赖 {module_name}（{purpose}）",
                "ok": ok,
                "hint": "pip install -r backend/requirements.txt",
            }
        )

    return {
        "all_ok": all(c["ok"] for c in checks),
        "checks": checks,
        "storage": store.snapshot(),
        "python_hint": "本项目要求 Python 3.13",
    }
