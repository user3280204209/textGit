"""画像智能体（需求点 1）：通过自然语言对话抽取多维度学生画像。

关键设计：
- 不用表单，从对话中抽取 → 这是需求明确要求的"摒弃传统繁琐表单"
- 每轮只追问缺失维度，抽满 6 个维度即达标
- 支持"随学随新"：已有维度会被新证据更新，而不是重建
"""

from __future__ import annotations

import json
import logging
import re

from app.agents.base import AgentContext, BaseAgent
from app.core.schemas import (
    ProfileDimension,
    ProfileItem,
    StudentProfile,
)

logger = logging.getLogger(__name__)

# 达到该数量即满足需求"不少于 6 个维度"
REQUIRED_DIMENSIONS = 6


class ProfileAgent(BaseAgent):
    """从对话中构建动态学生画像。"""

    name = "画像构建智能体"
    produces = None  # 画像不是"资源"，所以不产出 Resource
    temperature = 0.2  # 抽取任务要稳定，温度调低

    role_prompt = """你是一名学习分析专家，负责从学生的自然语言对话中抽取学习画像特征。

要求：
1. 只依据学生明确说出的内容抽取，不要臆测。信息不足就不要填。
2. 每个维度给出 0~1 的置信度：学生明确陈述给 0.9，间接推断给 0.5 以下。
3. 严格输出 JSON，不要任何解释文字、不要 markdown 代码块标记。

需要抽取的维度及含义：
- knowledge_base: 知识基础（已掌握什么、薄弱什么）
- cognitive_style: 认知风格（偏理论推导 / 偏实例操作 / 偏视觉图表）
- error_pattern: 易错点偏好（常在什么地方出错）
- learning_goal: 学习目标（想达到什么水平、为了什么）
- major_background: 专业背景
- learning_pace: 学习节奏（每周可投入时间、偏好快慢）
- resource_preference: 资源偏好（喜欢文档 / 视频 / 题目 / 代码）
- interest: 兴趣方向

输出格式（只输出这个 JSON）：
{
  "items": [
    {"dimension": "knowledge_base", "value": "描述", "confidence": 0.9, "evidence": ["学生原话片段"]}
  ],
  "next_question": "针对尚未明确的维度，提出一个自然的追问；若已足够则填 null"
}"""

    async def run(self, ctx: AgentContext) -> None:  # type: ignore[override]
        """执行一轮画像抽取，直接更新 ctx.profile。"""
        conversation = ctx.read("conversation", [])
        if not conversation:
            ctx.note(self.name, "无对话内容，跳过画像抽取")
            return None

        dialogue = "\n".join(f"{m['role']}: {m['content']}" for m in conversation)
        known = self._known_summary(ctx.profile)

        prompt = f"""已知画像信息（请在此基础上补充和修正，不要丢弃已有结论）：
{known}

最新对话内容：
{dialogue}

请抽取/更新画像，并给出下一个追问。"""

        raw = await self.call_llm(prompt)
        parsed = self._parse(raw)

        if parsed is None:
            ctx.note(self.name, "模型输出无法解析为 JSON，本轮画像未更新")
            return None

        updated = self._merge(ctx.profile, parsed.get("items", []))
        ctx.publish("next_question", parsed.get("next_question"))
        ctx.note(
            self.name,
            f"画像更新完成，当前 {ctx.profile.dimension_count} 个维度（本轮更新 {updated} 项）",
        )
        return None

    def _known_summary(self, profile: StudentProfile) -> str:
        if not profile.items:
            return "（暂无，这是首轮对话）"
        return "\n".join(f"- {d.value}: {i.value}" for d, i in profile.items.items())

    def _merge(self, profile: StudentProfile, items: list[dict]) -> int:
        """把新抽取的条目合并进画像，返回更新数量。

        合并策略：同维度用新值覆盖，但保留历史证据并叠加。
        这就是"随学随新"的实现。
        """
        updated = 0
        for raw_item in items:
            try:
                dimension = ProfileDimension(raw_item["dimension"])
            except (KeyError, ValueError):
                logger.warning("跳过非法维度: %s", raw_item)
                continue

            value = str(raw_item.get("value", "")).strip()
            if not value:
                continue

            evidence = [str(e) for e in raw_item.get("evidence", [])]
            existing = profile.items.get(dimension)

            if existing is not None:
                # 证据累加去重，避免同一句话反复堆叠
                merged_evidence = list(dict.fromkeys(existing.evidence + evidence))
                profile.items[dimension] = ProfileItem(
                    dimension=dimension,
                    value=value,
                    confidence=float(raw_item.get("confidence", 0.5)),
                    evidence=merged_evidence,
                )
            else:
                profile.items[dimension] = ProfileItem(
                    dimension=dimension,
                    value=value,
                    confidence=float(raw_item.get("confidence", 0.5)),
                    evidence=evidence,
                )
            updated += 1

        if updated:
            profile.version += 1
        return updated

    def _parse(self, raw: str) -> dict | None:
        """稳健地解析模型输出。

        LLM 经常在 JSON 外面包 ```json 或加解释文字，
        所以先尝试直接解析，失败再用正则抠出最外层花括号。
        """
        text = raw.strip()

        # 去掉 markdown 代码块围栏
        fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if fence:
            text = fence.group(1).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 兜底：抠出第一个 { 到最后一个 }
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                logger.warning("JSON 兜底解析仍失败: %s", text[:200])
        return None


def pick_next_question(profile: StudentProfile) -> str:
    """当模型没给追问时，用确定性逻辑补一个，保证对话能继续。

    这样即使 LLM 偷懒，接口也不会返回空追问导致对话卡死。
    """
    missing = [d for d in ProfileDimension if d not in profile.items]
    if not missing:
        return "你的画像已经比较完整了，我们可以开始生成学习资源了。"

    prompts = {
        ProfileDimension.KNOWLEDGE_BASE: "你在这门课上已经掌握了哪些内容？哪些地方感觉最吃力？",
        ProfileDimension.COGNITIVE_STYLE: "你更喜欢看理论推导，还是直接上手例子和代码？",
        ProfileDimension.ERROR_PATTERN: "做题或练习时，你通常容易在哪个环节出错？",
        ProfileDimension.LEARNING_GOAL: "你希望学完这门课达到什么程度？是为了考试还是项目实战？",
        ProfileDimension.MAJOR_BACKGROUND: "你的专业是什么？之前学过哪些相关课程？",
        ProfileDimension.LEARNING_PACE: "你每周大概能投入多少时间学习这门课？",
        ProfileDimension.RESOURCE_PREFERENCE: "你更喜欢哪种学习材料：文档、视频、题目还是代码案例？",
        ProfileDimension.INTEREST: "你对这门课的哪些方向最感兴趣？",
    }
    return prompts[missing[0]]
