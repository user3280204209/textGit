/**
 * 对话状态管理 —— 全项目最像"日常脚本"的一个文件。
 *
 * 你在终端里手写的那套：
 *
 *     messages = []
 *     messages.append({"role": "user", "content": q})          # ①
 *     resp = client.chat.completions.create(..., messages=messages)   # ②
 *     messages.append({"role": "assistant", "content": resp...})      # ③
 *
 * 下面这个 Hook 就是它的 Web 版：① ② ③ 一一对应，只是
 * `messages` 从普通列表变成了 React state（因为改它要触发重渲染）。
 *
 * 为什么单独抽成 Hook 而不是写在页面组件里？
 * 因为"对话逻辑"和"怎么显示"是两件事：
 *   - 以后要在资源页也挂一个提问框 → 直接复用这个 Hook，不用抄代码；
 *   - 想换成流式输出 → 只改这个文件，页面一行不用动。
 */

import { useCallback, useState } from "react";

import { api } from "@/api/client";
import type { ChatMessage, ChatUsage } from "@/types/api";

export interface UseChatResult {
  /** 完整对话历史。界面上渲染的就是它。 */
  messages: ChatMessage[];
  /** 是否正在等模型回复。用来禁用输入框、显示"正在思考" */
  isSending: boolean;
  /** 最近一次错误（已被 client.ts 翻译成中文） */
  error: string | null;
  /** 最近一次调用的 token 用量，用于在界面上展示"雪球滚多大了" */
  lastUsage: ChatUsage | null;
  send: (text: string) => Promise<void>;
  /** 重发最后一条悬空的用户消息（上一次请求失败时用） */
  retry: () => Promise<void>;
  /** 清空对话，重新开始滚雪球 */
  reset: () => void;
}

export function useChat(studentId = "demo-student"): UseChatResult {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUsage, setLastUsage] = useState<ChatUsage | null>(null);

  /**
   * 真正干活的一层。
   *
   * 刻意把"历史"作为参数传进来，而不是直接读 messages：
   * 这样这个函数不依赖任何外部状态，retry 才能安全地传一份"去掉尾巴"的历史。
   * （如果这里直接读 messages，retry 里 setMessages 是异步的，
   *   函数读到的仍是旧值，历史里会出现重复提问 —— 典型的闭包踩坑。）
   */
  const sendWith = useCallback(
    async (history: ChatMessage[], text: string): Promise<void> => {
      // ① 先把用户这句追加进历史 —— 雪球 +1
      const nextMessages: ChatMessage[] = [...history, { role: "user", content: text }];
      setMessages(nextMessages);
      setIsSending(true);
      setError(null);

      try {
        // ② 把**完整历史**发出去。后端不记得任何东西，全靠这一份。
        const data = await api.chat({
          messages: nextMessages,
          student_id: studentId,
        });

        // ③ 再把模型的回复追加进去 —— 雪球再 +1
        setMessages((prev) => [...prev, { role: "assistant", content: data.reply }]);
        setLastUsage(data.usage);
      } catch (err) {
        // client.ts 已经把 503/422/502 等都转成了可读中文，直接用
        setError(err instanceof Error ? err.message : "发送失败，请重试");
      } finally {
        setIsSending(false);
      }
    },
    [studentId],
  );

  /** 对外的主入口：拿当前历史 + 新输入，丢给 sendWith。 */
  const send = useCallback(
    async (text: string): Promise<void> => {
      const trimmed = text.trim();
      if (!trimmed || isSending) return;
      await sendWith(messages, trimmed);
    },
    [messages, isSending, sendWith],
  );

  /**
   * 重试：上一次请求失败时，最后一条会是"悬空的 user 消息"（没有对应的回复）。
   * 把它摘掉再重发，否则历史里会出现两条一模一样的提问。
   */
  const retry = useCallback(async (): Promise<void> => {
    const last = messages.at(-1);
    if (!last || last.role !== "user") return;
    await sendWith(messages.slice(0, -1), last.content);
  }, [messages, sendWith]);

  const reset = useCallback((): void => {
    setMessages([]);
    setError(null);
    setLastUsage(null);
  }, []);

  return { messages, isSending, error, lastUsage, send, retry, reset };
}
