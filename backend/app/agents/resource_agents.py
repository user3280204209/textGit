"""资源生成智能体集合（需求点 2）。

每个类只负责一种资源类型，职责单一 —— 这正是"多智能体"能被讲清楚的前提。
新增一种资源类型 = 新增一个类 + 在 registry 里注册一行，不用改调度逻辑。
"""

from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent
from app.core.schemas import Resource, ResourceStatus, ResourceType


class OutlineAgent(BaseAgent):
    """知识大纲智能体：不直接产出资源，但为下游所有智能体定框架。

    这是多智能体"协作"最直观的体现：先由它拆解知识点，
    后续文档/导图/题目/阅读/代码智能体都基于同一份大纲，
    保证 5 类资源口径一致（否则容易出现文档讲 A、题目考 B）。
    """

    name = "知识大纲智能体"
    produces = None
    temperature = 0.3

    role_prompt = """你是课程设计专家。请把给定主题拆解为适合该学生学习的大纲。

严格输出 JSON，不要 markdown 代码块：
{
  "outline": [
    {"title": "章节标题", "key_points": ["要点1", "要点2"], "difficulty": "基础|进阶|挑战"}
  ]
}

要求：4~6 个章节，由浅入深，章节之间要有逻辑递进关系。"""

    async def run(self, ctx: AgentContext) -> None:  # type: ignore[override]
        prompt = f"""学习主题：{ctx.topic}

学生画像：
{self.profile_brief(ctx)}

额外要求：{ctx.extra_requirements or "无"}

请生成课程大纲。"""

        raw = await self.call_llm(prompt)
        outline = self._parse_outline(raw)
        ctx.publish("outline", outline)
        ctx.note(self.name, f"产出 {len(outline)} 个章节的大纲，已发布到共享黑板")
        return None

    def _parse_outline(self, raw: str) -> list[dict]:
        import json
        import re

        text = raw.strip()
        fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if fence:
            text = fence.group(1).strip()

        for candidate in (text, text[text.find("{") : text.rfind("}") + 1]):
            try:
                data = json.loads(candidate)
                if isinstance(data, dict) and isinstance(data.get("outline"), list):
                    return data["outline"]
            except (json.JSONDecodeError, ValueError):
                continue

        # 兜底：解析失败也要保证下游有东西可用，避免整个任务链断掉
        return [
            {
                "title": self._fallback_title(raw),
                "key_points": ["核心概念", "典型应用"],
                "difficulty": "基础",
            }
        ]

    def _fallback_title(self, raw: str) -> str:
        first_line = next((ln.strip(" #*-") for ln in raw.splitlines() if ln.strip()), "")
        return first_line[:40] or "课程内容"


class LectureDocAgent(BaseAgent):
    """资源类型 1：专业课程讲解文档。"""

    name = "讲解文档智能体"
    produces = ResourceType.LECTURE_DOC
    temperature = 0.5

    role_prompt = """你是大学专业课程讲师，负责撰写结构化的课程讲解文档。

要求：
- 使用 Markdown，包含标题层级、要点列表、必要的公式（LaTeX）与代码块
- 必须针对学生的知识基础和认知风格调整讲法：
  基础薄弱 → 多用类比和生活例子；偏好理论 → 增加推导过程
- 每个章节末尾给出"小结"和"自测问题"
- 篇幅 1500 字以上，内容要具体，不要空话"""

    async def run(self, ctx: AgentContext) -> Resource:  # type: ignore[override]
        outline = ctx.read("outline", [])
        outline_text = self._format_outline(outline)

        prompt = f"""学习主题：{ctx.topic}

课程大纲：
{outline_text}

学生画像：
{self.profile_brief(ctx)}

额外要求：{ctx.extra_requirements or "无"}

请撰写完整的 Markdown 课程讲解文档。"""

        content = await self.call_llm(prompt)
        ctx.note(self.name, f"产出讲解文档 {len(content)} 字")
        return self.build_resource(ctx, f"{ctx.topic} - 课程讲解文档", content)

    def _format_outline(self, outline: list[dict]) -> str:
        if not outline:
            return "（无大纲，请自行组织结构）"
        lines = []
        for i, chapter in enumerate(outline, 1):
            title = chapter.get("title", f"第{i}章")
            points = "、".join(chapter.get("key_points", []))
            lines.append(f"{i}. {title}（难度：{chapter.get('difficulty', '未知')}）要点：{points}")
        return "\n".join(lines)


class MindMapAgent(BaseAgent):
    """资源类型 2：知识点思维导图。

    输出 Mermaid 文本而非图片：前端可直接渲染，
    既不需要系统级 Graphviz，也不需要在后端做图像处理。
    """

    name = "思维导图智能体"
    produces = ResourceType.MIND_MAP
    temperature = 0.4

    role_prompt = """你是知识结构化专家，负责生成 Mermaid 思维导图。

要求：
- 只输出 Mermaid 代码，使用 graph TD 或 mindmap 语法
- 节点文字简短（不超过 12 字），必须用中文
- 层次清晰：根节点 → 章节 → 关键要点
- 不要输出 ```mermaid 围栏之外的任何解释文字"""

    async def run(self, ctx: AgentContext) -> Resource:  # type: ignore[override]
        outline = ctx.read("outline", [])

        prompt = f"""主题：{ctx.topic}

需要体现在导图中的结构：
{self._format_outline(outline)}

学生认知风格：{self._cognitive_style(ctx)}

请生成 Mermaid 思维导图代码。"""

        mermaid = await self.call_llm(prompt)
        mermaid = self._clean(mermaid)
        ctx.note(self.name, "产出 Mermaid 思维导图源码（前端可直接渲染）")
        return self.build_resource(ctx, f"{ctx.topic} - 知识点思维导图", mermaid)

    def _cognitive_style(self, ctx: AgentContext) -> str:
        from app.core.schemas import ProfileDimension

        item = ctx.profile.items.get(ProfileDimension.COGNITIVE_STYLE)
        return item.value if item else "未知"

    def _format_outline(self, outline: list[dict]) -> str:
        if not outline:
            return "（无大纲，请根据主题自行结构化）"
        return "\n".join(
            f"- {c.get('title', '')}: {'、'.join(c.get('key_points', []))}" for c in outline
        )

    def _clean(self, raw: str) -> str:
        """剥掉模型可能加的 ```mermaid 围栏。"""
        import re

        text = raw.strip()
        fence = re.search(r"```(?:mermaid)?\s*(.*?)```", text, re.DOTALL)
        return fence.group(1).strip() if fence else text


class ExerciseAgent(BaseAgent):
    """资源类型 3：不同类型练习题目。

    刻意要求多种题型，对应需求里"不同类型练习题目"。
    """

    name = "练习题目智能体"
    produces = ResourceType.EXERCISE
    temperature = 0.7  # 出题需要多样性

    role_prompt = """你是命题专家，负责根据学生情况生成分层练习题。

要求：
- 至少包含 4 种题型：单选题、填空题、简答题、编程/应用题
- 每道题标注难度（基础/进阶/挑战）和对应知识点
- 必须附答案与解析，解析要针对学生的易错点
- 使用 Markdown 输出，题目和答案分区"""

    async def run(self, ctx: AgentContext) -> Resource:  # type: ignore[override]
        outline = ctx.read("outline", [])

        prompt = f"""主题：{ctx.topic}

知识点范围：
{self._format_outline(outline)}

学生画像（请重点针对薄弱点与易错点出题）：
{self.profile_brief(ctx)}

请生成练习题集。"""

        content = await self.call_llm(prompt)
        ctx.note(self.name, "产出分层练习题（含 4 种题型与答案解析）")
        return self.build_resource(ctx, f"{ctx.topic} - 分层练习题库", content)

    def _format_outline(self, outline: list[dict]) -> str:
        if not outline:
            return "（无大纲，请覆盖该主题核心知识点）"
        return "\n".join(
            f"- {c.get('title', '')}: {'、'.join(c.get('key_points', []))}" for c in outline
        )


class ReadingAgent(BaseAgent):
    """资源类型 4：拓展阅读材料。"""

    name = "拓展阅读智能体"
    produces = ResourceType.READING
    temperature = 0.6

    role_prompt = """你是学术资源推荐专家，负责编写拓展阅读材料。

要求：
- 包含三部分：延伸知识背景、经典文献/资料推荐（注明类型：教材/论文/官方文档/开源项目）、
  进阶学习方向
- 推荐资料必须真实存在且常见，不要编造不存在的论文标题或链接
- 结合学生兴趣方向做取舍，不要罗列一大堆
- Markdown 格式"""

    async def run(self, ctx: AgentContext) -> Resource:  # type: ignore[override]
        prompt = f"""主题：{ctx.topic}

学生画像：
{self.profile_brief(ctx)}

请编写拓展阅读材料。"""

        content = await self.call_llm(prompt)
        ctx.note(self.name, "产出拓展阅读材料")
        return self.build_resource(ctx, f"{ctx.topic} - 拓展阅读材料", content)


class CodeCaseAgent(BaseAgent):
    """资源类型 5：代码类实操案例。"""

    name = "代码案例智能体"
    produces = ResourceType.CODE_CASE
    temperature = 0.4

    role_prompt = """你是实战开发导师，负责编写可运行的代码实操案例。

要求：
- 提供完整可运行代码，不要伪代码或省略号
- 标注运行环境与依赖安装命令
- 代码中关键行要有中文注释
- 包含"运行结果说明"和"动手改造练习"
- 代码块必须标注语言"""

    async def run(self, ctx: AgentContext) -> Resource:  # type: ignore[override]
        prompt = f"""主题：{ctx.topic}

学生画像（据其基础调整案例难度）：
{self.profile_brief(ctx)}

请编写代码实操案例。"""

        content = await self.call_llm(prompt)
        ctx.note(self.name, "产出代码实操案例")
        return self.build_resource(ctx, f"{ctx.topic} - 代码实操案例", content)


class VideoAnimationAgent(BaseAgent):
    """资源类型 6：多模态教学视频/动画。

    这一类的策略与前面不同：不依赖本地重渲染工具链，
    而是产出"视频脚本 + 分镜 + 配图提示词"，并显式标记降级状态。
    这样在没配视频 API 的情况下依然有产物，答辩时不会被卡住。
    """

    name = "多模态视频智能体"
    produces = ResourceType.VIDEO_ANIMATION
    temperature = 0.7

    role_prompt = """你是教学视频编导，负责把知识点转化为可制作的教学视频方案。

要求输出三部分（Markdown）：
1. **视频脚本**：分镜表格，含镜头序号、画面描述、旁白文案、时长（秒）
2. **动画实现方案**：给出 Mermaid 或 HTML5/SVG 动画片段，能直接嵌入播放
3. **配图/配音提示词**：供文生图或 TTS 使用的提示词

总时长控制在 60~180 秒，聚焦最容易讲错的一个知识点。"""

    async def run(self, ctx: AgentContext) -> Resource:  # type: ignore[override]
        from app.core.config import settings

        prompt = f"""主题：{ctx.topic}

学生画像：
{self.profile_brief(ctx)}

请产出教学视频/动画方案。"""

        content = await self.call_llm(prompt)

        # 未配置多模态 API 时降级：产物仍可用（HTML5 动画可播），但状态如实标记
        if settings.multimodal_enabled:
            status = ResourceStatus.SUCCEEDED
            ctx.note(self.name, "已配置多模态 API，产出脚本与动画素材方案")
        else:
            status = ResourceStatus.DEGRADED
            ctx.note(
                self.name,
                "未配置多模态 API，降级为「脚本 + HTML5 动画」方案（可播放但非成片）",
            )

        return self.build_resource(
            ctx,
            f"{ctx.topic} - 教学视频/动画方案",
            content,
            status=status,
        )


class PathPlannerAgent(BaseAgent):
    """学习路径规划智能体（需求点 3）。

    读取黑板上已生成的全部资源，按依赖顺序排出学习步骤。
    """

    name = "路径规划智能体"
    produces = None
    temperature = 0.3

    role_prompt = """你是学习规划师，负责为学生制定个性化学习路径。

严格输出 JSON，不要 markdown 代码块：
{
  "steps": [
    {"order": 1, "title": "步骤标题", "objective": "本步目标",
     "resource_titles": ["使用的资源标题"], "estimated_minutes": 45}
  ],
  "rationale": "整体规划理由，要引用学生的具体画像特征"
}

要求：4~8 步，由浅入深；每一步都要说明为什么这样安排；
必须把已有的资源分配到具体步骤中。"""

    async def run(self, ctx: AgentContext) -> None:  # type: ignore[override]
        resources = ctx.read("resources", [])
        resource_list = "\n".join(f"- {r.title}（{r.resource_type.value}）" for r in resources)

        prompt = f"""学习目标：{ctx.read("goal", ctx.topic)}

学生画像：
{self.profile_brief(ctx)}

已生成的可用资源：
{resource_list or "（暂无，请按主题设计步骤）"}

请生成学习路径。"""

        raw = await self.call_llm(prompt)
        path_data = self._parse(raw)
        ctx.publish("path", path_data)
        steps = path_data.get("steps", []) if path_data else []
        ctx.note(self.name, f"产出 {len(steps)} 步学习路径")
        return None

    def _parse(self, raw: str) -> dict | None:
        import json
        import re

        text = raw.strip()
        fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if fence:
            text = fence.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start, end = text.find("{"), text.rfind("}")
            if start != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    return None
        return None
