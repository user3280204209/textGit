"""画像接口（需求点 1：对话式学习画像自主构建）。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.agents import AgentContext
from app.agents.profile_agent import REQUIRED_DIMENSIONS, ProfileAgent, pick_next_question
from app.core.llm import LLMNotConfiguredError
from app.core.schemas import ProfileChatRequest, ProfileChatResponse, StudentProfile
from app.store import store

router = APIRouter(prefix="/profile", tags=["画像"])


@router.post("/chat", response_model=ProfileChatResponse, summary="对话式构建/更新画像")
async def chat(request: ProfileChatRequest) -> ProfileChatResponse:
    """通过一轮自然语言对话抽取并更新学生画像。

    对话历史会被保留，因此学生可以"随学随新"地持续修正画像。
    """
    profile = store.get_profile(request.student_id)

    # 把本轮对话并入历史
    for message in request.messages:
        store.append_message(request.student_id, message.role, message.content)

    conversation = store.get_conversation(request.student_id)

    ctx = AgentContext(
        student_id=request.student_id,
        topic="画像构建",
        profile=profile,
    )
    ctx.publish("conversation", conversation)

    try:
        await ProfileAgent().run(ctx)  # type: ignore[arg-type]
    except LLMNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    store.save_profile(profile)

    next_question = ctx.read("next_question") or pick_next_question(profile)
    is_complete = profile.is_complete(REQUIRED_DIMENSIONS)

    reply = (
        f"画像已更新，目前覆盖 {profile.dimension_count} 个维度（要求 {REQUIRED_DIMENSIONS} 个）。"
    )
    if is_complete:
        reply += "维度已达标，可以开始生成学习资源了。"

    return ProfileChatResponse(
        reply=reply,
        profile=profile,
        is_complete=is_complete,
        next_question=None if is_complete else next_question,
    )


@router.get("/{student_id}", response_model=StudentProfile, summary="查询画像")
async def get_profile(student_id: str) -> StudentProfile:
    return store.get_profile(student_id)


@router.delete("/{student_id}", summary="重置画像（便于演示）")
async def reset_profile(student_id: str) -> dict[str, str]:
    store.save_profile(StudentProfile(student_id=student_id))
    store._conversations.pop(student_id, None)  # noqa: SLF001 - 演示用重置
    return {"status": "reset", "student_id": student_id}
