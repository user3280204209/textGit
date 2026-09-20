"""领域数据结构：全组共享的"契约"。

这里定义的模型同时被三处使用，所以改动会影响所有人：
1. 后端业务逻辑
2. FastAPI 自动生成的 OpenAPI 文档
3. 前端 TypeScript 类型（见 frontend/src/types/api.ts）

⚠️ 改这里的字段名，必须同步改前端 types，否则前端静默拿到 undefined。
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


# ============================================================
# 学生画像（需求点 1：≥6 个维度）
# ============================================================
class ProfileDimension(StrEnum):
    """画像维度。需求要求不少于 6 个，这里定义 8 个以保证达标。

    新增维度只需在这里加一个枚举值 + 在 ProfileAgent 的提示词里加一项。
    """

    KNOWLEDGE_BASE = "knowledge_base"  # 知识基础
    COGNITIVE_STYLE = "cognitive_style"  # 认知风格
    ERROR_PATTERN = "error_pattern"  # 易错点偏好
    LEARNING_GOAL = "learning_goal"  # 学习目标
    MAJOR_BACKGROUND = "major_background"  # 专业背景
    LEARNING_PACE = "learning_pace"  # 学习节奏
    RESOURCE_PREFERENCE = "resource_preference"  # 资源偏好
    INTEREST = "interest"  # 兴趣方向


class ProfileItem(BaseModel):
    """单个维度的画像条目。"""

    dimension: ProfileDimension
    value: str = Field(description="该维度的当前结论")
    confidence: float = Field(
        default=0.5, ge=0.0, le=1.0, description="置信度，低置信度不应用于强推送"
    )
    evidence: list[str] = Field(default_factory=list, description="支撑该结论的对话原文片段")
    updated_at: datetime = Field(default_factory=datetime.now)


class StudentProfile(BaseModel):
    """动态学生画像（支持随学随新）。"""

    student_id: str
    items: dict[ProfileDimension, ProfileItem] = Field(default_factory=dict)
    version: int = 1
    updated_at: datetime = Field(default_factory=datetime.now)

    @property
    def dimension_count(self) -> int:
        """已填充的维度数量，用于校验是否满足"不少于 6 个维度"。"""
        return len(self.items)

    def is_complete(self, minimum: int = 6) -> bool:
        return self.dimension_count >= minimum


# ============================================================
# 学习资源（需求点 2：≥5 类资源生成）
# ============================================================
class ResourceType(StrEnum):
    """资源类型。需求要求至少 5 种，这里定义 6 种。"""

    LECTURE_DOC = "lecture_doc"  # 专业课程讲解文档
    MIND_MAP = "mind_map"  # 知识点思维导图
    EXERCISE = "exercise"  # 练习题目
    READING = "reading"  # 拓展阅读材料
    VIDEO_ANIMATION = "video_animation"  # 多模态教学视频/动画
    CODE_CASE = "code_case"  # 代码类实操案例


class ResourceStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEGRADED = "degraded"  # 无法完成时降级（如视频→图文），必须显式标记


class Resource(BaseModel):
    """一份生成好的学习资源。"""

    resource_id: str
    resource_type: ResourceType
    title: str
    content: str = Field(default="", description="Markdown / HTML / 代码正文")
    url: str | None = Field(default=None, description="产出的文件或视频地址")
    status: ResourceStatus = ResourceStatus.PENDING
    produced_by_agent: str = Field(default="", description="产出该资源的智能体名，用于答辩演示协作")
    trace: list[str] = Field(default_factory=list, description="生成过程留痕，便于展示多智能体协作")
    created_at: datetime = Field(default_factory=datetime.now)
    error: str | None = None


# ============================================================
# 学习路径（需求点 3）
# ============================================================
class PathStep(BaseModel):
    order: int
    title: str
    objective: str
    resource_ids: list[str] = Field(default_factory=list)
    estimated_minutes: int = 30
    done: bool = False


class LearningPath(BaseModel):
    student_id: str
    goal: str
    steps: list[PathStep] = Field(default_factory=list)
    rationale: str = Field(default="", description="规划理由，答辩时是加分点")
    generated_at: datetime = Field(default_factory=datetime.now)


# ============================================================
# API 请求 / 响应
# ============================================================
class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant|system)$")
    content: str


class ProfileChatRequest(BaseModel):
    student_id: str
    messages: list[ChatMessage]


class ProfileChatResponse(BaseModel):
    reply: str
    profile: StudentProfile
    is_complete: bool = Field(description="是否已满足 ≥6 维度")
    next_question: str | None = Field(default=None, description="下一个待补全维度的追问")


class GenerateRequest(BaseModel):
    student_id: str
    topic: str
    resource_types: list[ResourceType] = Field(
        default_factory=lambda: [
            ResourceType.LECTURE_DOC,
            ResourceType.MIND_MAP,
            ResourceType.EXERCISE,
            ResourceType.READING,
            ResourceType.CODE_CASE,
        ],
        description="默认 5 类，满足需求下限",
    )
    extra_requirements: str = ""


class GenerateResponse(BaseModel):
    task_id: str
    status: ResourceStatus


class TaskResult(BaseModel):
    task_id: str
    status: ResourceStatus
    resources: list[Resource] = Field(default_factory=list)
    agent_log: list[str] = Field(default_factory=list, description="多智能体协作日志")


class PathRequest(BaseModel):
    student_id: str
    goal: str
    available_resource_ids: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str = "ok"
    app_name: str
    env: str
    llm_configured: bool
    multimodal_enabled: bool
