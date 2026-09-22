/**
 * 统一的 API 客户端。
 *
 * 约定：所有网络请求都必须走这里，不要在组件里直接写 fetch/axios。
 * 好处：
 *   - 后端地址、超时、错误格式只有一处定义
 *   - 后端返回 503（未配 Key）时前端能拿到可读提示
 *   - 后续加鉴权 token 只改这一个文件
 */

import axios, { AxiosError } from "axios";
import type {
  ChatRequest,
  ChatResponse,
  EnvCheckResponse,
  GenerateRequest,
  GenerateResponse,
  HealthResponse,
  LearningPath,
  PathRequest,
  ProfileChatRequest,
  ProfileChatResponse,
  Resource,
  StudentProfile,
  TaskResult,
} from "@/types/api";

/** Vite 会把 /api 代理到后端 8000，所以这里用相对路径即可 */
const client = axios.create({
  baseURL: "/api",
  timeout: 60_000,
  headers: { "Content-Type": "application/json" },
});

/** 把后端错误统一转成可读中文，避免界面直接显示 "Request failed 503" */
export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

client.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string }>) => {
    const status = error.response?.status;
    const detail = error.response?.data?.detail;

    if (status === 503) {
      return Promise.reject(
        new ApiError(
          detail ?? "后端未配置 LLM API Key，请在 backend/.env 中填写 LLM_API_KEY",
          503,
        ),
      );
    }
    if (status === 404) {
      return Promise.reject(new ApiError(detail ?? "请求的资源不存在", 404));
    }
    if (status === 422) {
      return Promise.reject(new ApiError(detail ?? "请求参数不合法，请检查字段", 422));
    }
    if (error.code === "ECONNABORTED") {
      return Promise.reject(new ApiError("请求超时，后端可能仍在生成中", status));
    }
    if (!error.response) {
      return Promise.reject(
        new ApiError("无法连接后端，请确认 uvicorn 已在 8000 端口启动"),
      );
    }
    return Promise.reject(new ApiError(detail ?? error.message, status));
  },
);

export const api = {
  // ---- 系统 ----
  async health(): Promise<HealthResponse> {
    const { data } = await client.get<HealthResponse>("/health");
    return data;
  },

  async envCheck(): Promise<EnvCheckResponse> {
    const { data } = await client.get<EnvCheckResponse>("/env-check");
    return data;
  },

  // ---- 画像 ----
  async chatProfile(payload: ProfileChatRequest): Promise<ProfileChatResponse> {
    const { data } = await client.post<ProfileChatResponse>("/profile/chat", payload);
    return data;
  },

  async getProfile(studentId: string): Promise<StudentProfile> {
    const { data } = await client.get<StudentProfile>(`/profile/${studentId}`);
    return data;
  },

  async resetProfile(studentId: string): Promise<void> {
    await client.delete(`/profile/${studentId}`);
  },

  // ---- 直连对话 ----
  /**
   * 发一轮对话。
   *
   * 注意签名：传进去的是**完整历史**（含本轮用户提问），不是单条消息。
   * 后端无状态，它不知道也不关心你之前聊过什么。
   *
   * 超时单独放宽到 120 秒：默认的 60 秒对长回答偏紧，
   * 而且这里一旦超时，用户只会看到"失败"，体验很差。
   */
  async chat(payload: ChatRequest): Promise<ChatResponse> {
    const { data } = await client.post<ChatResponse>("/chat", payload, {
      timeout: 120_000,
    });
    return data;
  },

  // ---- 资源生成 ----
  async generateResources(payload: GenerateRequest): Promise<GenerateResponse> {
    const { data } = await client.post<GenerateResponse>("/resources/generate", payload);
    return data;
  },

  async getTask(taskId: string): Promise<TaskResult> {
    const { data } = await client.get<TaskResult>(`/resources/tasks/${taskId}`);
    return data;
  },

  async listResources(taskId: string): Promise<Resource[]> {
    const { data } = await client.get<Resource[]>(`/resources/tasks/${taskId}/resources`);
    return data;
  },

  // ---- 学习路径 ----
  async planPath(payload: PathRequest): Promise<LearningPath> {
    const { data } = await client.post<LearningPath>("/path/plan", payload);
    return data;
  },
};

/**
 * 轮询任务直到结束。
 *
 * 生成 5 类资源要几十秒，后端设计成异步任务，
 * 前端必须轮询而不是干等一个 HTTP 请求。
 */
export async function pollTask(
  taskId: string,
  options: { intervalMs?: number; timeoutMs?: number } = {},
): Promise<TaskResult> {
  const interval = options.intervalMs ?? 2000;
  const timeout = options.timeoutMs ?? 300_000;
  const started = Date.now();

  while (Date.now() - started < timeout) {
    const task = await api.getTask(taskId);
    if (task.status === "succeeded" || task.status === "failed") {
      return task;
    }
    await new Promise((resolve) => setTimeout(resolve, interval));
  }
  throw new ApiError("生成超时，请稍后到任务列表查看结果");
}
