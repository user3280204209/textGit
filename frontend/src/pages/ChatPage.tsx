/**
 * 对话页 —— 把状态、列表、输入框拼在一起。
 *
 * 这个文件里没有一行"业务逻辑"：发消息在 useChat，渲染单条在 MessageBubble，
 * 收集输入在 ChatInput。它只负责三件事：
 *   1. 按顺序摆好它们；
 *   2. 新消息到来时自动滚到底部；
 *   3. 把 token 用量显示出来（让"雪球"看得见）。
 */

import { useEffect, useRef } from "react";

import ChatInput from "@/components/ChatInput";
import MessageBubble from "@/components/MessageBubble";
import { useChat } from "@/hooks/useChat";

export default function ChatPage() {
  const { messages, isSending, error, lastUsage, send, retry, reset } = useChat();
  const bottomRef = useRef<HTMLDivElement>(null);

  // 消息变化或状态变化时滚到底部。
  // 依赖 isSending 是为了让"正在思考…"出现时也滚过去。
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, isSending, error]);

  return (
    <div className="chat">
      <header className="chat__header">
        <div>
          <h1 className="chat__title">AI 对话</h1>
          <p className="muted chat__stats">
            共 {messages.length} 条消息
            {lastUsage
              ? ` · 上次消耗 ${lastUsage.total_tokens} tokens（提问 ${lastUsage.prompt_tokens} + 回答 ${lastUsage.completion_tokens}）`
              : ""}
          </p>
        </div>
        <button
          className="btn-ghost"
          type="button"
          onClick={reset}
          disabled={messages.length === 0 || isSending}
        >
          清空对话
        </button>
      </header>

      <div className="chat__list">
        {messages.length === 0 && !error && (
          <div className="chat__empty">
            <p>还没有消息，发一句试试。</p>
            <p className="muted">
              然后连着聊两三轮，注意看上面 token 数怎么涨 ——
              那正是"每次把完整历史发过去"的代价。
            </p>
          </div>
        )}

        {/*
          用 index 当 key：这里是可以的，因为列表只会在末尾追加。
          如果以后支持"删除中间某条消息"，就必须换成稳定 id，
          否则 React 复用错组件，会出现内容串位。
        */}
        {messages.map((message, index) => (
          <MessageBubble key={index} message={message} />
        ))}

        {isSending && <div className="chat__typing">AI 正在思考…</div>}

        {error && (
          <div className="chat__error">
            <span className="chat__error-text">⚠️ {error}</span>
            <button
              className="btn-ghost"
              type="button"
              onClick={retry}
              disabled={isSending}
            >
              重试
            </button>
          </div>
        )}

        {/* 滚动锚点：一个空 div，scrollIntoView 的目标 */}
        <div ref={bottomRef} />
      </div>

      <ChatInput onSend={send} disabled={isSending} />
    </div>
  );
}
