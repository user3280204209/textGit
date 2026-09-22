/**
 * 输入框 + 发送按钮。
 *
 * 这里只管一件事：把用户敲的字收集起来，通过 onSend 交出去。
 * 它**不**调用任何接口、**不**知道对话历史 —— 发送逻辑全在 useChat.ts。
 *
 * 草稿文本（draft）故意放在组件内部，而不是提升到 useChat：
 * 用户打字不该触发整个对话列表重渲染。
 */

import { useState, type KeyboardEvent } from "react";

interface ChatInputProps {
  /** 交给父组件的发送回调（实际就是 useChat 的 send） */
  onSend: (text: string) => void;
  /** 模型正在回复时禁用，避免并发请求把历史搅乱 */
  disabled: boolean;
}

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [draft, setDraft] = useState("");

  function submit(): void {
    const text = draft.trim();
    if (!text || disabled) return;
    onSend(text);
    // 立刻清空：用户消息会马上出现在列表里，输入框留着旧内容会显得没反应
    setDraft("");
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>): void {
    // Enter 发送、Shift+Enter 换行 —— 和常见聊天工具一致
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <div className="composer">
      <textarea
        className="composer__input"
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="说点什么…（Enter 发送，Shift+Enter 换行）"
        rows={3}
        disabled={disabled}
      />
      <button
        className="composer__send"
        type="button"
        onClick={submit}
        disabled={disabled || draft.trim().length === 0}
      >
        {disabled ? "生成中…" : "发送"}
      </button>
    </div>
  );
}
