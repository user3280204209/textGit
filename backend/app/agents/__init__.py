"""agents 包：多智能体定义与注册表。"""

from app.agents.base import AgentContext, BaseAgent
from app.agents.profile_agent import ProfileAgent
from app.agents.resource_agents import (
    CodeCaseAgent,
    ExerciseAgent,
    LectureDocAgent,
    MindMapAgent,
    OutlineAgent,
    PathPlannerAgent,
    ReadingAgent,
    VideoAnimationAgent,
)

#: 资源类型 → 智能体类的注册表。
#: 新增资源类型只需在 schemas.ResourceType 加枚举 + 在这里加一行，
#: 编排层无需改动（开闭原则，也是答辩时可以讲的设计点）。
RESOURCE_AGENT_REGISTRY: dict[str, type[BaseAgent]] = {
    "lecture_doc": LectureDocAgent,
    "mind_map": MindMapAgent,
    "exercise": ExerciseAgent,
    "reading": ReadingAgent,
    "code_case": CodeCaseAgent,
    "video_animation": VideoAnimationAgent,
}

__all__ = [
    "AgentContext",
    "BaseAgent",
    "CodeCaseAgent",
    "ExerciseAgent",
    "LectureDocAgent",
    "MindMapAgent",
    "OutlineAgent",
    "PathPlannerAgent",
    "ProfileAgent",
    "RESOURCE_AGENT_REGISTRY",
    "ReadingAgent",
    "VideoAnimationAgent",
]
