"""LLM 客户端工厂：全项目唯一的模型入口。

为什么单独抽出来：
1. 换供应商（DeepSeek → 通义 → OpenAI）只改 .env，业务代码不动；
2. 统一加上重试与超时，避免每个 agent 各写一遍；
3. 没有 Key 时抛出明确错误，而不是让调用方收到难懂的 SDK 报错。
"""

from __future__ import annotations

import logging
from functools import lru_cache

from langchain_openai import ChatOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMNotConfiguredError(RuntimeError):
    """未配置 API Key 时抛出，让上层返回可读提示。"""


@lru_cache
def get_llm(temperature: float | None = None) -> ChatOpenAI:
    """返回带重试配置的 ChatOpenAI 实例（OpenAI 兼容协议）。

    Args:
        temperature: 覆盖默认温度。生成题目建议调高，抽取画像建议调低。
    """
    if not settings.llm_configured:
        raise LLMNotConfiguredError("未检测到 LLM_API_KEY。请在 backend/.env 中填写后再调用模型。")

    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=settings.llm_temperature if temperature is None else temperature,
        timeout=settings.agent_timeout_seconds,
        max_retries=2,
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    reraise=True,
)
async def ainvoke_with_retry(llm: ChatOpenAI, messages: list) -> str:
    """带指数退避的异步调用。

    LLM 接口在高峰期会 429 / 超时，没重试会直接失败给用户。
    """
    response = await llm.ainvoke(messages)
    content = response.content
    # 部分供应商返回 list[dict] 结构，统一成字符串
    if isinstance(content, list):
        return "".join(
            part.get("text", "") if isinstance(part, dict) else str(part) for part in content
        )
    return str(content)
