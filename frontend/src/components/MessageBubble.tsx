/**
 * 单条消息气泡。
 *
 * 这个组件只做一件事：把一条 ChatMessage 画出来。
 * 它不知道对话有几条、也不知道怎么发消息 —— 所以永远不会有 bug 藏在这里。
 */

import type { ChatMessage } from "@/types/api";

/** 不同角色在界面上的显示名。加新角色时只改这里。 */
const ROLE_LABELS: Record<ChatMessage["role"], string> = {
  user: "我",
  assistant: "AI",
  system: "系统",
};

interface MessageBubbleProps {
  message: ChatMessage;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={`bubble-row bubble-row--${isUser ? "user" : "assistant"}`}>
      <div className="bubble-row__role">{ROLE_LABELS[message.role]}</div>
      <div className={`bubble bubble--${isUser ? "user" : "assistant"}`}>
        {/* 内容用 pre-wrap 渲染，保留模型输出里的换行和缩进 */}
        {message.content}
      </div>
    </div>
  );
}
