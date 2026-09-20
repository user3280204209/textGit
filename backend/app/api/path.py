"""学习路径接口（需求点 3：个性化学习路径规划与资源推送）。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.llm import LLMNotConfiguredError
from app.core.schemas import LearningPath, PathRequest, PathStep
from app.graph import Orchestrator
from app.store import store

router = APIRouter(prefix="/path", tags=["学习路径"])


@router.post("/plan", response_model=LearningPath, summary="生成个性化学习路径")
async def plan(request: PathRequest) -> LearningPath:
    """基于画像与已生成资源，规划学习步骤。

    若路径规划智能体返回异常，降级为按资源类型排序的确定性路径，
    保证接口永远有可用结果（答辩演示不能因为这个环节挂掉）。
    """
    profile = store.get_profile(request.student_id)
    resources = store.all_resources(request.student_id)

    try:
        orchestrator = Orchestrator()
        path_data, _ = await orchestrator.plan_path(
            student_id=request.student_id,
            profile=profile,
            goal=request.goal,
            resources=resources,
        )
    except LLMNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    steps = _to_steps(path_data, resources)
    rationale = str(path_data.get("rationale", "")) if path_data else ""

    if not steps:
        steps = _fallback_steps(request.goal, resources)
        rationale = rationale or "（模型未返回有效路径，已按资源类型给出默认学习顺序）"

    return LearningPath(
        student_id=request.student_id,
        goal=request.goal,
        steps=steps,
        rationale=rationale,
    )


def _to_steps(path_data: dict, resources: list) -> list[PathStep]:
    """把模型输出的步骤转成强类型对象，并尽力关联资源 id。"""
    raw_steps = path_data.get("steps", []) if isinstance(path_data, dict) else []
    if not isinstance(raw_steps, list):
        return []

    title_to_id = {r.title: r.resource_id for r in resources}
    steps: list[PathStep] = []

    for index, raw in enumerate(raw_steps, start=1):
        if not isinstance(raw, dict):
            continue
        titles = raw.get("resource_titles", []) or []
        steps.append(
            PathStep(
                order=int(raw.get("order", index)),
                title=str(raw.get("title", f"步骤 {index}")),
                objective=str(raw.get("objective", "")),
                resource_ids=[title_to_id[t] for t in titles if t in title_to_id],
                estimated_minutes=int(raw.get("estimated_minutes", 30)),
            )
        )
    return steps


def _fallback_steps(goal: str, resources: list) -> list[PathStep]:
    """确定性兜底路径：按"先看懂 → 再练 → 再拓展 → 再动手"的认知顺序。"""
    order = [
        ("lecture_doc", "通读讲解文档，建立整体认知"),
        ("mind_map", "用思维导图梳理知识结构"),
        ("video_animation", "观看动画讲解，突破难点"),
        ("exercise", "完成分层练习，检验掌握程度"),
        ("code_case", "动手实现案例，形成肌肉记忆"),
        ("reading", "拓展阅读，加深理解"),
    ]
    steps: list[PathStep] = []
    idx = 1
    for rtype, objective in order:
        matched = [r for r in resources if r.resource_type.value == rtype]
        if not matched:
            continue
        steps.append(
            PathStep(
                order=idx,
                title=matched[0].title,
                objective=objective,
                resource_ids=[r.resource_id for r in matched],
                estimated_minutes=45,
            )
        )
        idx += 1
    return steps
