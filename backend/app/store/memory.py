"""轻量存储层。

当前实现：进程内字典。
为什么先用它而不是直接上数据库：
组员小白众多，第一天就要能跑起来。数据库迁移（Alembic）会引入
额外的失败点。等接口稳定后再把这一层替换为 SQLAlchemy 实现，
上层业务代码不用改 —— 这是刻意留的接缝。

⚠️ 重启后端数据即丢失，仅用于开发联调。答辩演示前务必确认
   是走数据库版本还是接受重启丢数据。
"""

from __future__ import annotations

import uuid
from typing import Any

from app.core.schemas import Resource, ResourceStatus, StudentProfile, TaskResult


class InMemoryStore:
    """线程/协程安全的极简存储。"""

    def __init__(self) -> None:
        self._profiles: dict[str, StudentProfile] = {}
        self._conversations: dict[str, list[dict[str, str]]] = {}
        self._tasks: dict[str, TaskResult] = {}

    # ---- 画像 ----
    def get_profile(self, student_id: str) -> StudentProfile:
        if student_id not in self._profiles:
            self._profiles[student_id] = StudentProfile(student_id=student_id)
        return self._profiles[student_id]

    def save_profile(self, profile: StudentProfile) -> None:
        self._profiles[profile.student_id] = profile

    def get_conversation(self, student_id: str) -> list[dict[str, str]]:
        return self._conversations.setdefault(student_id, [])

    def append_message(self, student_id: str, role: str, content: str) -> None:
        self.get_conversation(student_id).append({"role": role, "content": content})

    # ---- 生成任务 ----
    def create_task(self) -> str:
        task_id = uuid.uuid4().hex[:12]
        self._tasks[task_id] = TaskResult(
            task_id=task_id,
            status=ResourceStatus.PENDING,
        )
        return task_id

    def get_task(self, task_id: str) -> TaskResult | None:
        return self._tasks.get(task_id)

    def update_task(
        self,
        task_id: str,
        status: ResourceStatus | None = None,
        resources: list[Resource] | None = None,
        agent_log: list[str] | None = None,
    ) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return
        if status is not None:
            task.status = status
        if resources is not None:
            task.resources = resources
        if agent_log is not None:
            task.agent_log = agent_log

    def list_resources(self, task_id: str) -> list[Resource]:
        task = self._tasks.get(task_id)
        return task.resources if task else []

    def all_resources(self, student_id: str | None = None) -> list[Resource]:
        """汇总所有任务的资源，供路径规划使用。"""
        out: list[Resource] = []
        for task in self._tasks.values():
            out.extend(task.resources)
        return out

    def snapshot(self) -> dict[str, Any]:
        """调试用快照。"""
        return {
            "profiles": len(self._profiles),
            "tasks": len(self._tasks),
        }


#: 全局单例。替换为数据库实现时只改这一行。
store = InMemoryStore()
