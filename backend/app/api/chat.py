"""直连对话接口：全项目最短、最好懂的一条链路。

    useChat.ts 的 messages[]
        └─► POST /api/chat
              └─► client.chat.completions.create(...)
                    └─► DeepSeek /chat/completions
                          └─► 返回 { reply, model, usage }

为什么单独开这个文件、而不塞进 agents/ 的 LangGraph？
--------------------------------------------------
"能在网页里聊天"和"多智能体协同生成资源"是两个难度完全不同的问题。
先把最简单的通道做到 100% 可跑通，复杂编排再长在旁边。
这条通道只有一层，出问题时排查成本最低 —— 这是刻意的取舍。

⚠️ 本文件刻意不做提示词工程。
system 提示由前端放进 messages 里传过来，后端只管转发。
等第 4 步做"学习助手人格"时，再决定提示词放前端还是抽到后端。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from openai import APIConnectionError, APIStatusError

from app.core.config import settings
from app.core.llm import LLMNotConfiguredError, get_async_client
from app.core.schemas import ChatRequest, ChatResponse, ChatUsage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["对话"])

#: 把 SDK 的错误码翻译成人能看懂的话。前端 client.ts 会把它显示在气泡里。
_STATUS_HINTS = {
    400: "请求格式不被模型接受",
    401: "API Key 无效，请检查 backend/.env 里的 LLM_API_KEY",
    402: "账户余额不足，请到模型服务商处充值",
    404: "模型名不存在，请检查 backend/.env 里的 LLM_MODEL",
    429: "请求过于频繁（限流），稍后再试",
    500: "模型服务端内部错误，稍后重试",
    503: "模型服务暂时不可用，稍后重试",
}


@router.post("", response_model=ChatResponse, summary="直连对话（滚雪球模式）")
async def chat(request: ChatRequest) -> ChatResponse:
    """一问一答：收完整历史，只返回新生成的一句。

    这里**不修改** request.messages，也**不返回**新的历史数组。
    雪球由前端自己滚（把 reply append 进去即可），后端保持无状态。

    这个决定的好处：同一个接口天然支持以后要加的
    "重新生成上一条""编辑历史后重发"——因为后端从不假设自己拥有历史。
    """
    try:
        client = get_async_client()

        # ↓↓↓ 下面这几行就是日常脚本里的写法，原样搬进来 ↓↓↓
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[m.model_dump() for m in request.messages],  # type: ignore[arg-type]
            temperature=(
                settings.llm_temperature if request.temperature is None else request.temperature
            ),
        )
        # ↑↑↑ 差别只有一个：前面多了 await，因为是异步接口 ↑↑↑

    except LLMNotConfiguredError as exc:
        # 503：服务器自己没配好，不是调用方的错，所以给可读提示而不是 500
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    except APIStatusError as exc:
        # 401 / 402 / 429 这类"Key 或额度"问题，必须让用户一眼看懂
        hint = _STATUS_HINTS.get(exc.status_code, f"模型服务返回 {exc.status_code}")
        logger.warning("LLM 调用失败 status=%s msg=%s", exc.status_code, exc.message)
        raise HTTPException(status_code=502, detail=f"{hint}（{exc.message}）") from exc

    except APIConnectionError as exc:
        # 网络不通 / base_url 写错：最常见的两种新手事故
        raise HTTPException(
            status_code=502,
            detail=f"无法连接模型服务 {settings.llm_base_url}，请检查网络或 base_url 配置",
        ) from exc

    reply = response.choices[0].message.content or ""
    usage = response.usage
    token_usage = ChatUsage(
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
        total_tokens=usage.total_tokens if usage else 0,
    )

    logger.info(
        "对话完成 | model=%s | 请求轮数=%d | tokens=%d",
        response.model,
        len(request.messages),
        token_usage.total_tokens,
    )

    return ChatResponse(reply=reply, model=response.model, usage=token_usage)
