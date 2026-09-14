"""多智能体编排层：把各个角色智能体串成一次完整的生成流程。

为什么用 LangGraph 而不是直接顺序 await：
需求要求"多智能体协同"，而协同必然涉及：
  - 有依赖的串行（大纲 → 各资源）
  - 无依赖的并行（5 类资源互相不依赖）
  - 失败隔离（一个智能体挂了不能让整个任务失败）
LangGraph 的 StateGraph 把这些显式建模成图，答辩时可以直接画出来。

⚠️ 重要实现说明：
LangGraph 0.2+ 用 TypedDict 作为 State。
本文件里的 graph 用于「结构化展示协作拓扑」，
实际执行走 asyncio 以保证并行与失败隔离更直观可控 ——
两者职责分开，避免把初学者绕晕。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, TypedDict

from app.agents import RESOURCE_AGENT_REGISTRY, AgentContext
from app.agents.base import BaseAgent
from app.agents.resource_agents import OutlineAgent, PathPlannerAgent
from app.core.config import settings
from app.core.schemas import Resource, ResourceStatus, ResourceType, StudentProfile

logger = logging.getLogger(__name__)


class GenerationState(TypedDict, total=False):
    """LangGraph 状态定义（用于可视化协作拓扑）。

    这是"多智能体架构"的显式声明：
    每个字段代表流程中的一个共享数据槽位。
    """

    student_id: str
    topic: str
    profile: StudentProfile
    resource_types: list[ResourceType]
    outline: list[dict[str, Any]]
    resources: list[Resource]
    path: dict[str, Any]
    logs: list[str]
    errors: list[str]


class Orchestrator:
    """多智能体调度器。"""

    def __init__(self, max_concurrency: int | None = None) -> None:
        self.max_concurrency = max_concurrency or settings.max_concurrent_agents

    async def generate(
        self,
        student_id: str,
        topic: str,
        profile: StudentProfile,
        resource_types: list[ResourceType],
        extra_requirements: str = "",
    ) -> tuple[list[Resource], list[str]]:
        """执行一次完整的资源生成。

        Returns:
            (资源列表, 协作日志)
        """
        ctx = AgentContext(
            student_id=student_id,
            topic=topic,
            profile=profile,
            extra_requirements=extra_requirements,
        )

        # ---- 阶段 1：大纲先行（串行，下游全部依赖它）----
        await self._run_agent_safely(OutlineAgent(), ctx)

        # ---- 阶段 2：多资源并行生成（体现协同 + 效率）----
        resource_agents = self._build_agents(resource_types)
        ctx.note(
            "调度器",
            f"启动 {len(resource_agents)} 个资源智能体并行协作（并发上限 {self.max_concurrency}）",
        )

        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def guarded(agent: BaseAgent) -> Resource | None:
            async with semaphore:
                return await self._run_agent_safely(agent, ctx)

        results = await asyncio.gather(*(guarded(a) for a in resource_agents))
        resources = [r for r in results if r is not None]
        ctx.publish("resources", resources)

        # 统计必须按状态区分，不能只数长度 ——
        # 失败项也会以 FAILED 资源的形式返回（便于前端展示"哪一类失败了"），
        # 若只数 len(resources)，全部失败也会被误报成"成功 N/N"。
        succeeded = [r for r in resources if r.status == ResourceStatus.SUCCEEDED]
        degraded = [r for r in resources if r.status == ResourceStatus.DEGRADED]
        failed = [r for r in resources if r.status == ResourceStatus.FAILED]

        summary = f"成功 {len(succeeded)}/{len(resource_agents)} 项"
        if degraded:
            summary += f"，降级 {len(degraded)} 项"
        if failed:
            summary += f"，失败 {len(failed)} 项"
        ctx.note("调度器", f"资源生成完成：{summary}")

        return resources, ctx.log

    async def plan_path(
        self,
        student_id: str,
        profile: StudentProfile,
        goal: str,
        resources: list[Resource],
    ) -> tuple[dict[str, Any], list[str]]:
        """生成学习路径（需求点 3）。"""
        ctx = AgentContext(student_id=student_id, topic=goal, profile=profile)
        ctx.publish("resources", resources)
        ctx.publish("goal", goal)

        await self._run_agent_safely(PathPlannerAgent(), ctx)
        return ctx.read("path") or {}, ctx.log

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _build_agents(self, resource_types: list[ResourceType]) -> list[BaseAgent]:
        """按请求的资源类型实例化对应智能体。

        找不到对应智能体时跳过并记日志，而不是抛异常 ——
        这样前端传了暂未实现的类型也不会 500。
        """
        agents: list[BaseAgent] = []
        for rtype in resource_types:
            agent_cls = RESOURCE_AGENT_REGISTRY.get(rtype.value)
            if agent_cls is None:
                logger.warning("资源类型 %s 暂无对应智能体，已跳过", rtype.value)
                continue
            agents.append(agent_cls())
        return agents

    async def _run_agent_safely(self, agent: BaseAgent, ctx: AgentContext) -> Resource | None:
        """执行单个智能体，隔离失败。

        失败隔离是必需的：视频智能体最容易挂（依赖外部 API），
        它挂掉不应该影响文档/题目等其它资源的产出。
        """
        try:
            return await asyncio.wait_for(
                agent.run(ctx),  # type: ignore[arg-type]
                timeout=settings.agent_timeout_seconds,
            )
        except TimeoutError:
            message = f"执行超时（>{settings.agent_timeout_seconds}s）"
            logger.error("%s %s", agent.name, message)
            ctx.note(agent.name, f"❌ {message}")
            return self._failed_resource(agent, ctx, message)
        except Exception as exc:  # noqa: BLE001 - 兜底隔离，必须捕获全部异常
            logger.exception("%s 执行失败", agent.name)
            ctx.note(agent.name, f"❌ 执行失败：{exc}")
            return self._failed_resource(agent, ctx, str(exc))

    def _failed_resource(self, agent: BaseAgent, ctx: AgentContext, error: str) -> Resource | None:
        """为失败的资源智能体生成一条失败记录。

        返回失败资源而不是 None，是为了让前端能显示"哪一类资源失败了"，
        而不是静默少一项。
        """
        if agent.produces is None:
            return None
        resource = agent.build_resource(
            ctx,
            title=f"{ctx.topic} - {agent.produces.value}（生成失败）",
            content="",
            status=ResourceStatus.FAILED,
        )
        resource.error = error
        return resource
