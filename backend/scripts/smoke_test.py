"""端到端自检脚本：一次性验证脚手架是否真的可用。

用途
----
技术负责人 / CI 在交付前跑一次，确认：
  1. 应用能启动
  2. 三大核心接口（画像 / 资源 / 路径）响应正常
  3. 需求硬性指标达标（≥6 维度、≥5 类资源）
  4. 未配置 Key 时降级行为正确（不是 500）

跑法（在 backend 目录下）：
    python scripts/smoke_test.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# 把 backend 根目录加入 sys.path，这样无论在哪个目录执行本脚本都能 import app
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

PASS = "  [PASS]"
FAIL = "  [FAIL]"


class Checker:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.passed = 0

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        if condition:
            self.passed += 1
            print(f"{PASS} {name}" + (f" — {detail}" if detail else ""))
        else:
            self.failures.append(name)
            print(f"{FAIL} {name}" + (f" — {detail}" if detail else ""))

    def report(self) -> int:
        print()
        print("=" * 60)
        if self.failures:
            print(f"存在 {len(self.failures)} 项未通过：")
            for item in self.failures:
                print(f"  - {item}")
            print("=" * 60)
            return 1
        print(f"全部通过（{self.passed} 项）")
        print("=" * 60)
        return 0


def main() -> int:
    checker = Checker()

    with TestClient(app) as client:
        # ---------------- 1. 基础连通 ----------------
        print("\n[1/6] 基础连通性")

        root = client.get("/")
        checker.check("根路径可访问", root.status_code == 200)

        health = client.get("/api/health")
        checker.check("健康检查可用", health.status_code == 200)
        health_body = health.json()
        checker.check(
            "健康检查返回必需字段",
            {"status", "llm_configured", "multimodal_enabled"} <= health_body.keys(),
            f"llm_configured={health_body.get('llm_configured')}",
        )

        docs = client.get("/docs")
        checker.check("Swagger 文档可访问", docs.status_code == 200)

        # ---------------- 2. 需求硬性指标 ----------------
        print("\n[2/6] 需求硬性指标")

        from app.core.schemas import ProfileDimension, ResourceType

        dims = list(ProfileDimension)
        checker.check(
            "画像维度 ≥ 6（需求点 1）",
            len(dims) >= 6,
            f"实际 {len(dims)} 个",
        )

        types = client.get("/api/resources/types")
        checker.check("资源类型接口可用", types.status_code == 200)
        if types.status_code == 200:
            body = types.json()
            checker.check(
                "资源类型 ≥ 5（需求点 2）",
                len(body["types"]) >= 5,
                f"实际 {len(body['types'])} 类",
            )
            checker.check("声明了下限值", body.get("minimum_required") == 5)

        checker.check(
            "资源类型枚举与接口一致",
            len(list(ResourceType)) == len(types.json()["types"]),
        )

        # ---------------- 3. 智能体注册完整性 ----------------
        print("\n[3/6] 智能体注册完整性")

        from app.agents import RESOURCE_AGENT_REGISTRY

        missing = [rt.value for rt in ResourceType if rt.value not in RESOURCE_AGENT_REGISTRY]
        checker.check(
            "每种资源类型都有对应智能体",
            not missing,
            f"缺失: {missing}" if missing else f"{len(RESOURCE_AGENT_REGISTRY)} 个已注册",
        )

        # ---------------- 4. 画像接口 ----------------
        print("\n[4/6] 画像接口（需求点 1）")

        profile = client.get("/api/profile/smoke-student")
        checker.check("查询画像可用", profile.status_code == 200)
        checker.check(
            "新学生画像为空（不造假数据）",
            len(profile.json()["items"]) == 0,
        )

        chat = client.post(
            "/api/profile/chat",
            json={
                "student_id": "smoke-student",
                "messages": [{"role": "user", "content": "我是计算机专业大二学生"}],
            },
        )
        # 未配置 Key 时必须是 503（可读提示），而不是 500（崩溃）
        checker.check(
            "未配置 Key 时返回 503 而非 500",
            chat.status_code in (200, 503),
            f"状态码 {chat.status_code}",
        )
        if chat.status_code == 503:
            checker.check(
                "503 带可读中文提示",
                "LLM_API_KEY" in str(chat.json().get("detail", "")),
            )

        # ---------------- 5. 资源生成接口 ----------------
        print("\n[5/6] 资源生成接口（需求点 2）")

        gen = client.post(
            "/api/resources/generate",
            json={
                "student_id": "smoke-student",
                "topic": "机器学习基础",
                "resource_types": [rt.value for rt in ResourceType],
            },
        )
        checker.check("生成任务提交可用", gen.status_code == 200, f"状态码 {gen.status_code}")

        if gen.status_code == 200:
            task_id = gen.json()["task_id"]
            task = client.get(f"/api/resources/tasks/{task_id}")
            checker.check("任务状态可查询", task.status_code == 200)

        checker.check(
            "不存在的任务返回 404",
            client.get("/api/resources/tasks/nonexistent").status_code == 404,
        )

        # ---------------- 6. 学习路径接口 ----------------
        print("\n[6/6] 学习路径接口（需求点 3）")

        path = client.post(
            "/api/path/plan",
            json={"student_id": "smoke-student", "goal": "掌握机器学习基础"},
        )
        checker.check(
            "路径接口可用（无 Key 时 503，有 Key 时 200）",
            path.status_code in (200, 503),
            f"状态码 {path.status_code}",
        )

    # ---------------- 环境自检接口 ----------------
    print("\n[附加] 环境自检接口")
    with TestClient(app) as client:
        env_check = client.get("/api/env-check")
        checker.check("环境自检可用", env_check.status_code == 200)
        if env_check.status_code == 200:
            body = env_check.json()
            checker.check(
                "自检项都带排查提示",
                all("hint" in c for c in body["checks"]),
                f"{len(body['checks'])} 项检查",
            )
            not_ok = [c["item"] for c in body["checks"] if not c["ok"]]
            if not_ok:
                print(f"        （未通过项，属正常：{', '.join(not_ok)}）")

    return checker.report()


if __name__ == "__main__":
    sys.exit(main())
