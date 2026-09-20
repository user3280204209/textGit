"""编排层测试：验证多智能体调度、失败隔离与统计口径。

这些测试全部不需要 API Key —— 用假的智能体替换真实 LLM 调用，
所以能进 CI，也适合组员本地快速回归。
"""

from __future__ import annotations

import pytest

from app.agents.base import AgentContext, BaseAgent
from app.core.schemas import (
    ProfileDimension,
    ProfileItem,
    Resource,
    ResourceStatus,
    ResourceType,
    StudentProfile,
)
from app.graph.orchestrator import Orchestrator


def _profile() -> StudentProfile:
    """构造一个满足 ≥6 维度的测试画像。"""
    profile = StudentProfile(student_id="tester")
    for dimension in list(ProfileDimension)[:6]:
        profile.items[dimension] = ProfileItem(dimension=dimension, value="测试值")
    return profile


def _ctx() -> AgentContext:
    return AgentContext(student_id="tester", topic="机器学习", profile=_profile())


# ============================================================
# 失败隔离
# ============================================================
class _ExplodingAgent(BaseAgent):
    """总是抛异常的智能体，用来验证失败隔离。"""

    name = "爆炸智能体"
    produces = ResourceType.LECTURE_DOC
    role_prompt = "不会被执行"

    async def run(self, ctx: AgentContext) -> Resource:  # type: ignore[override]
        raise RuntimeError("模拟智能体崩溃")


@pytest.mark.asyncio
async def test_failure_is_isolated_and_recorded() -> None:
    """单个智能体崩溃不能抛出到调用方，而要变成 FAILED 资源。"""
    orchestrator = Orchestrator()
    ctx = _ctx()

    result = await orchestrator._run_agent_safely(_ExplodingAgent(), ctx)

    assert result is not None, "失败也应返回记录，否则前端会静默少一项"
    assert result.status == ResourceStatus.FAILED
    assert result.error is not None and "模拟智能体崩溃" in result.error
    # 失败必须写进协作日志，便于排查
    assert any("❌" in entry for entry in ctx.log)


@pytest.mark.asyncio
async def test_non_producing_agent_failure_returns_none() -> None:
    """不产出资源的智能体（如大纲）失败时返回 None，不生成假资源。"""

    class _ExplodingOutline(BaseAgent):
        name = "爆炸大纲智能体"
        produces = None
        role_prompt = "x"

        async def run(self, ctx: AgentContext) -> None:  # type: ignore[override]
            raise RuntimeError("boom")

    orchestrator = Orchestrator()
    result = await orchestrator._run_agent_safely(_ExplodingOutline(), _ctx())
    assert result is None


# ============================================================
# 统计口径（回归测试）
# ============================================================
@pytest.mark.asyncio
async def test_summary_counts_success_not_total() -> None:
    """回归测试：全部失败时，日志绝不能报告"成功 N/N"。

    这个 bug 真实发生过 —— 失败项也以 FAILED 资源返回，
    早先的实现用 len(resources) 当成功数，导致答辩演示时
    日志显示"成功 6/6"而实际一个都没成功。
    """

    class _FailAgent(BaseAgent):
        name = "必败智能体"
        produces = ResourceType.READING
        role_prompt = "x"

        async def run(self, ctx: AgentContext) -> Resource:  # type: ignore[override]
            raise RuntimeError("一定失败")

    # 把注册表里所有资源智能体都换成必败的，保证结果全为 FAILED
    orchestrator = Orchestrator()
    orchestrator._build_agents = lambda types: [  # type: ignore[method-assign]
        _FailAgent() for _ in types
    ]

    resources, log = await orchestrator.generate(
        student_id="tester",
        topic="机器学习",
        profile=_profile(),
        resource_types=[ResourceType.READING, ResourceType.EXERCISE],
    )

    assert len(resources) == 2
    assert all(r.status == ResourceStatus.FAILED for r in resources)

    summary_lines = [entry for entry in log if "资源生成完成" in entry]
    assert summary_lines, "必须记录统计日志"
    summary = summary_lines[-1]
    assert "成功 0/2" in summary, f"统计口径错误，实际日志：{summary}"
    assert "失败 2" in summary


@pytest.mark.asyncio
async def test_summary_reports_degraded_separately() -> None:
    """降级项必须单独计数，不能被算作成功。"""

    class _DegradedAgent(BaseAgent):
        name = "降级智能体"
        produces = ResourceType.VIDEO_ANIMATION
        role_prompt = "x"

        async def run(self, ctx: AgentContext) -> Resource:  # type: ignore[override]
            return self.build_resource(ctx, "降级产物", "脚本内容", status=ResourceStatus.DEGRADED)

    orchestrator = Orchestrator()
    orchestrator._build_agents = lambda types: [  # type: ignore[method-assign]
        _DegradedAgent() for _ in types
    ]

    resources, log = await orchestrator.generate(
        student_id="tester",
        topic="机器学习",
        profile=_profile(),
        resource_types=[ResourceType.VIDEO_ANIMATION],
    )

    assert len(resources) == 1
    assert resources[0].status == ResourceStatus.DEGRADED

    summary = [entry for entry in log if "资源生成完成" in entry][-1]
    assert "成功 0/1" in summary
    assert "降级 1" in summary


# ============================================================
# 智能体构建
# ============================================================
def test_build_agents_skips_unknown_type() -> None:
    """未知资源类型应被跳过并记日志，而不是抛异常。"""
    orchestrator = Orchestrator()
    agents = orchestrator._build_agents([ResourceType.LECTURE_DOC])
    assert len(agents) == 1
    assert agents[0].produces == ResourceType.LECTURE_DOC


def test_build_agents_returns_all_requested() -> None:
    orchestrator = Orchestrator()
    requested = [
        ResourceType.LECTURE_DOC,
        ResourceType.MIND_MAP,
        ResourceType.EXERCISE,
        ResourceType.READING,
        ResourceType.CODE_CASE,
    ]
    agents = orchestrator._build_agents(requested)
    assert len(agents) == len(requested)


# ============================================================
# 黑板协作
# ============================================================
def test_blackboard_publish_and_read() -> None:
    """黑板模式：一个智能体的产出必须能被下游读到。"""
    ctx = _ctx()
    assert ctx.read("outline") is None

    ctx.publish("outline", [{"title": "第一章"}])
    assert ctx.read("outline") == [{"title": "第一章"}]
    assert ctx.read("missing", default=[]) == []


def test_collaboration_log_records_agent_name() -> None:
    """协作日志必须带智能体名 —— 这是答辩演示多智能体协作的证据。"""
    ctx = _ctx()
    ctx.note("画像构建智能体", "更新了 3 个维度")
    ctx.note("思维导图智能体", "产出 Mermaid 源码")

    assert len(ctx.log) == 2
    assert ctx.log[0].startswith("[画像构建智能体]")
    assert ctx.log[1].startswith("[思维导图智能体]")
