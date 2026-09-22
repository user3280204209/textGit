"""聚合所有 API 路由。

新增功能模块时，只需在这里 include_router 一行。
"""

from fastapi import APIRouter

from app.api import chat, path, profile, resources, system

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(chat.router)  # 直连对话（最简通道，前端聊天页用这条）
api_router.include_router(profile.router)
api_router.include_router(resources.router)
api_router.include_router(path.router)

__all__ = ["api_router"]
