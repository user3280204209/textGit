"""资源生成接口（需求点 2：多智能体协同的资源生成）。

生成耗时较长（5 类资源 × LLM 调用），所以采用「提交任务 → 轮询结果」
的异步模式，而不是让 HTTP 请求挂几十秒（会触发网关超时）。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.core.llm import LLMNotConfiguredError
from app.core.schemas import (
    GenerateRequest,
    GenerateResponse,
    Resource,
    ResourceStatus,
    TaskResult,
)
from app.graph import Orchestrator
from app.store import store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resources", tags=["资源生成"])


@router.post("/generate", response_model=GenerateResponse, summary="提交资源生成任务")
async def generate(
    request: GenerateRequest,
    background: BackgroundTasks,
) -> GenerateResponse:
    """提交生成任务，立即返回 task_id。

    前端拿到 task_id 后轮询 /resources/tasks/{task_id} 获取进度与结果。
    """
    profile = store.get_profile(request.student_id)
    task_id = store.create_task()
    store.update_task(task_id, status=ResourceStatus.RUNNING)

    background.add_task(
        _run_generation,
        task_id,
        request,
        profile,
    )

    return GenerateResponse(task_id=task_id, status=ResourceStatus.RUNNING)


async def _run_generation(task_id: str, request: GenerateRequest, profile) -> None:  # type: ignore[no-untyped-def]
    """后台执行生成。任何异常都必须落到任务状态上，否则前端会一直转圈。"""
    try:
        orchestrator = Orchestrator()
        resources, agent_log = await orchestrator.generate(
            student_id=request.student_id,
            topic=request.topic,
            profile=profile,
            resource_types=request.resource_types,
            extra_requirements=request.extra_requirements,
        )

        # 只要没有任何一项成功，整体判定失败
        succeeded = [r for r in resources if r.status == ResourceStatus.SUCCEEDED]
        overall = ResourceStatus.SUCCEEDED if succeeded else ResourceStatus.FAILED

        store.update_task(task_id, status=overall, resources=resources, agent_log=agent_log)

    except LLMNotConfiguredError as exc:
        logger.error("LLM 未配置，任务 %s 失败", task_id)
        store.update_task(
            task_id,
            status=ResourceStatus.FAILED,
            agent_log=[f"❌ {exc}"],
        )
    except Exception as exc:  # noqa: BLE001 - 后台任务必须兜底
        logger.exception("任务 %s 执行异常", task_id)
        store.update_task(
            task_id,
            status=ResourceStatus.FAILED,
            agent_log=[f"❌ 任务异常：{exc}"],
        )


@router.get("/tasks/{task_id}", response_model=TaskResult, summary="查询任务结果")
async def get_task(task_id: str) -> TaskResult:
    task = store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")
    return task


@router.get("/tasks/{task_id}/resources", response_model=list[Resource], summary="任务产出列表")
async def list_resources(task_id: str) -> list[Resource]:
    if store.get_task(task_id) is None:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")
    return store.list_resources(task_id)


@router.get("/types", summary="支持的资源类型")
async def list_types() -> dict[str, Any]:
    """让前端动态渲染"可生成哪几类资源"，避免前后端硬编码两份清单。

    ⚠️ 返回类型必须写 Any / 具体模型，不能写 dict[str, list[...]]：
    本接口同时返回 types（列表）和 minimum_required（整数），
    标注成纯列表会让 FastAPI 的响应校验直接抛 500。
    """
    from app.core.schemas import ResourceType

    labels = {
        ResourceType.LECTURE_DOC: "专业课程讲解文档",
        ResourceType.MIND_MAP: "知识点思维导图",
        ResourceType.EXERCISE: "分层练习题库",
        ResourceType.READING: "拓展阅读材料",
        ResourceType.VIDEO_ANIMATION: "多模态教学视频/动画",
        ResourceType.CODE_CASE: "代码实操案例",
    }
    return {
        "types": [{"value": t.value, "label": labels[t]} for t in ResourceType],
        "minimum_required": 5,
    }
