"""智能体基类：所有角色智能体都继承它。

设计意图（答辩要点）：
需求要求"多智能体协同"而非"一个提示词干完所有事"。
这里用统一的 BaseAgent 抽象，让每个角色智能体：
  - 有自己的 name / role_prompt / 负责的资源类型
  - 统一接收 AgentContext（含学生画像 + 共享黑板）
  - 统一把产出写回黑板，供后续智能体复用
这样"协作"是可被观察和演示的，而不是黑盒。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.core.llm import ainvoke_with_retry, get_llm
from app.core.schemas import Resource, ResourceStatus, ResourceType, StudentProfile

logger = logging.getLogger(__name__)


@dataclass
class AgentContext:
    """智能体之间传递的共享上下文（黑板模式）。

    为什么用黑板而不是函数返回值串起来：
    多个资源生成智能体需要同时读同一份学生画像 + 已生成的知识大纲，
    黑板让它们解耦，也方便加新智能体而不改老代码。
    """

    student_id: str
    topic: str
    profile: StudentProfile
    extra_requirements: str = ""
    # 黑板：键为逻辑名，值为任意产出。例如 {"outline": [...], "key_points": [...]}
    blackboard: dict[str, Any] = field(default_factory=dict)
    # 协作日志：记录"谁产出了什么"，直接用于答辩演示与结果接口
    log: list[str] = field(default_factory=list)

    def note(self, agent_name: str, message: str) -> None:
        """写一条协作日志。"""
        entry = f"[{agent_name}] {message}"
        self.log.append(entry)
        logger.info(entry)

    def publish(self, key: str, value: Any) -> None:
        """把产出放到黑板上，供下游智能体读取。"""
        self.blackboard[key] = value

    def read(self, key: str, default: Any = None) -> Any:
        return self.blackboard.get(key, default)


class BaseAgent(ABC):
    """角色智能体抽象基类。"""

    #: 智能体显示名，会出现在协作日志里
    name: str = "base_agent"
    #: 该智能体负责产出的资源类型；None 表示它不直接产出资源（如画像/规划）
    produces: ResourceType | None = None
    #: 角色提示词，子类必须定义
    role_prompt: str = ""

    def __init__(self, temperature: float | None = None) -> None:
        self.temperature = temperature

    @abstractmethod
    async def run(self, ctx: AgentContext) -> Resource | None:
        """执行本智能体的职责。

        Returns:
            产出的资源；若本智能体不负责产出资源则返回 None。
        """
        raise NotImplementedError

    async def call_llm(self, user_prompt: str) -> str:
        """调用 LLM，自动套用本智能体的角色提示词。"""
        llm = get_llm(self.temperature)
        messages = [
            ("system", self.role_prompt),
            ("human", user_prompt),
        ]
        return await ainvoke_with_retry(llm, messages)

    def build_resource(
        self,
        ctx: AgentContext,
        title: str,
        content: str,
        status: ResourceStatus = ResourceStatus.SUCCEEDED,
        url: str | None = None,
    ) -> Resource:
        """构造统一格式的资源对象。"""
        return Resource(
            resource_id=f"{self.name}-{abs(hash((ctx.student_id, ctx.topic, title))) % 10**8}",
            resource_type=self.produces or ResourceType.LECTURE_DOC,
            title=title,
            content=content,
            url=url,
            status=status,
            produced_by_agent=self.name,
            trace=[entry for entry in ctx.log if entry.startswith(f"[{self.name}]")],
        )

    def profile_brief(self, ctx: AgentContext) -> str:
        """把画像压缩成提示词片段。

        所有资源生成智能体都调它 —— 这是"个性化"真正落地的地方：
        画像不是展示用的装饰，而是实际进入每个生成提示词。
        """
        if not ctx.profile.items:
            return "（暂无画像信息，请按通用大学生水平生成）"

        lines = []
        for dim, item in ctx.profile.items.items():
            confidence = f"{item.confidence:.0%}"
            lines.append(f"- {dim.value}: {item.value}（置信度 {confidence}）")
        return "\n".join(lines)
