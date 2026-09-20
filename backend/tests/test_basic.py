"""基础测试：不依赖 LLM API Key，CI 与本地都能跑。

跑法（在 backend 目录下）：
    pytest
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.schemas import (
    ProfileDimension,
    ProfileItem,
    ResourceType,
    StudentProfile,
)
from app.main import app

client = TestClient(app)


# ============================================================
# 基础连通性
# ============================================================
def test_root() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "app" in response.json()


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    # 未配置 Key 时必须如实报告 false，而不是假装健康
    assert "llm_configured" in body


def test_env_check_shape() -> None:
    response = client.get("/api/env-check")
    assert response.status_code == 200
    body = response.json()
    assert "checks" in body
    assert isinstance(body["checks"], list)
    assert len(body["checks"]) > 0
    # 每条检查都必须带排查提示，否则对小白无用
    for check in body["checks"]:
        assert {"item", "ok", "hint"} <= check.keys()


# ============================================================
# 需求符合性：这些测试直接对应老师的功能要求
# ============================================================
def test_resource_types_cover_requirement() -> None:
    """需求要求至少 5 种资源类型。"""
    response = client.get("/api/resources/types")
    assert response.status_code == 200
    body = response.json()
    assert len(body["types"]) >= 5
    assert body["minimum_required"] == 5


def test_profile_dimensions_cover_requirement() -> None:
    """需求要求画像不少于 6 个维度。"""
    assert len(ProfileDimension) >= 6


def test_profile_completeness_logic() -> None:
    """画像达标判定逻辑。"""
    profile = StudentProfile(student_id="test-student")

    # 空画像必须判定为未达标
    assert not profile.is_complete(6)
    assert profile.dimension_count == 0

    # 填满 6 个维度后达标
    for dimension in list(ProfileDimension)[:6]:
        profile.items[dimension] = ProfileItem(dimension=dimension, value="测试值")
    assert profile.is_complete(6)
    assert profile.dimension_count == 6


def test_get_profile_empty() -> None:
    response = client.get("/api/profile/new-student-xyz")
    assert response.status_code == 200
    assert response.json()["student_id"] == "new-student-xyz"


def test_task_not_found() -> None:
    response = client.get("/api/resources/tasks/not-exist")
    assert response.status_code == 404


# ============================================================
# 智能体注册表：确保每种资源类型都有智能体，否则生成会静默少项
# ============================================================
def test_every_resource_type_has_agent() -> None:
    """这是防回归的关键测试。

    如果有人在 schemas 里加了一种资源类型却忘了在注册表登记，
    前端能选但生成时会被静默跳过 —— 这个测试会立刻报错。
    """
    from app.agents import RESOURCE_AGENT_REGISTRY

    for resource_type in ResourceType:
        assert resource_type.value in RESOURCE_AGENT_REGISTRY, (
            f"资源类型 {resource_type.value} 没有对应的智能体，"
            f"请在 app/agents/__init__.py 的 RESOURCE_AGENT_REGISTRY 中注册"
        )


def test_agents_declare_produces() -> None:
    """每个资源智能体都必须声明自己产出的资源类型。"""
    from app.agents import RESOURCE_AGENT_REGISTRY

    for value, agent_cls in RESOURCE_AGENT_REGISTRY.items():
        assert agent_cls.produces is not None
        assert agent_cls.produces.value == value


def test_path_fallback_works_without_llm() -> None:
    """路径规划的确定性兜底必须独立可用（不依赖 LLM）。"""
    from app.api.path import _fallback_steps
    from app.core.schemas import Resource

    resources = [
        Resource(
            resource_id="r1",
            resource_type=ResourceType.LECTURE_DOC,
            title="讲解文档",
        ),
        Resource(
            resource_id="r2",
            resource_type=ResourceType.EXERCISE,
            title="练习题",
        ),
    ]
    steps = _fallback_steps("测试目标", resources)
    assert len(steps) == 2
    # 认知顺序：讲解文档必须排在练习题之前
    assert steps[0].resource_ids == ["r1"]
    assert steps[1].resource_ids == ["r2"]
