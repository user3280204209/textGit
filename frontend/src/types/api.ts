/**
 * 后端 API 类型定义。
 *
 * ⚠️ 对齐规则（重要）：
 * 本文件必须与 backend/app/core/schemas.py 保持一致。
 * 后端改了字段名而这里没改，前端会静默拿到 undefined，
 * 报错信息还很难查 —— 所以两边必须同一次提交里一起改。
 *
 * 校验方式：跑 `pnpm typecheck`，再对照后端 /docs 里的 Schema。
 */

// ============================================================
// 画像（需求点 1）
// ============================================================
export const PROFILE_DIMENSIONS = [
  "knowledge_base",
  "cognitive_style",
  "error_pattern",
  "learning_goal",
  "major_background",
  "learning_pace",
  "resource_preference",
  "interest",
] as const;

export type ProfileDimension = (typeof PROFILE_DIMENSIONS)[number];

/** 维度中文名，用于界面展示 */
export const PROFILE_DIMENSION_LABELS: Record<ProfileDimension, string> = {
  knowledge_base: "知识基础",
  cognitive_style: "认知风格",
  error_pattern: "易错点偏好",
  learning_goal: "学习目标",
  major_background: "专业背景",
  learning_pace: "学习节奏",
  resource_preference: "资源偏好",
  interest: "兴趣方向",
};

/** 需求要求的最少维度数 */
export const REQUIRED_DIMENSION_COUNT = 6;

export interface ProfileItem {
  dimension: ProfileDimension;
  value: string;
  confidence: number;
  evidence: string[];
  updated_at: string;
}

export interface StudentProfile {
  student_id: string;
  items: Partial<Record<ProfileDimension, ProfileItem>>;
  version: number;
  updated_at: string;
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface ProfileChatRequest {
  student_id: string;
  messages: ChatMessage[];
}

export interface ProfileChatResponse {
  reply: string;
  profile: StudentProfile;
  is_complete: boolean;
  next_question: string | null;
}

// ============================================================
// 直连对话（对应 backend/app/api/chat.py）
// ============================================================
// ⚠️ 必须与 backend/app/core/schemas.py 里的 ChatRequest / ChatResponse / ChatUsage 对齐。
//
// 注意这里没有"会话 id"的概念：因为后端**不存历史**，
// 完整对话由前端那个 messages 数组携带（滚雪球）。

/** token 用量。放在界面上是为了让"雪球越滚越贵"这件事看得见。 */
export interface ChatUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface ChatRequest {
  /** 完整对话历史。注意是"完整"，不是"最新一条"。 */
  messages: ChatMessage[];
  /** 会话归属，第 3 步接持久化时才真正用上 */
  student_id?: string;
  /** 留空则用后端 .env 里的 LLM_TEMPERATURE */
  temperature?: number;
}

export interface ChatResponse {
  reply: string;
  /** 实际使用的模型名，用于确认"换没换成功" */
  model: string;
  usage: ChatUsage;
}

// ============================================================
// 资源（需求点 2）
// ============================================================
export const RESOURCE_TYPES = [
  "lecture_doc",
  "mind_map",
  "exercise",
  "reading",
  "video_animation",
  "code_case",
] as const;

export type ResourceType = (typeof RESOURCE_TYPES)[number];

export const RESOURCE_TYPE_LABELS: Record<ResourceType, string> = {
  lecture_doc: "专业课程讲解文档",
  mind_map: "知识点思维导图",
  exercise: "分层练习题库",
  reading: "拓展阅读材料",
  video_animation: "多模态教学视频/动画",
  code_case: "代码实操案例",
};

export type ResourceStatus = "pending" | "running" | "succeeded" | "failed" | "degraded";

export const RESOURCE_STATUS_LABELS: Record<ResourceStatus, string> = {
  pending: "排队中",
  running: "生成中",
  succeeded: "已完成",
  failed: "失败",
  degraded: "已降级",
};

export interface Resource {
  resource_id: string;
  resource_type: ResourceType;
  title: string;
  content: string;
  url: string | null;
  status: ResourceStatus;
  produced_by_agent: string;
  trace: string[];
  created_at: string;
  error: string | null;
}

export interface GenerateRequest {
  student_id: string;
  topic: string;
  resource_types: ResourceType[];
  extra_requirements?: string;
}

export interface GenerateResponse {
  task_id: string;
  status: ResourceStatus;
}

export interface TaskResult {
  task_id: string;
  status: ResourceStatus;
  resources: Resource[];
  /** 多智能体协作日志 —— 答辩演示时直接展示这个 */
  agent_log: string[];
}

// ============================================================
// 学习路径（需求点 3）
// ============================================================
export interface PathStep {
  order: number;
  title: string;
  objective: string;
  resource_ids: string[];
  estimated_minutes: number;
  done: boolean;
}

export interface LearningPath {
  student_id: string;
  goal: string;
  steps: PathStep[];
  rationale: string;
  generated_at: string;
}

export interface PathRequest {
  student_id: string;
  goal: string;
  available_resource_ids?: string[];
}

// ============================================================
// 系统
// ============================================================
export interface HealthResponse {
  status: string;
  app_name: string;
  env: string;
  llm_configured: boolean;
  multimodal_enabled: boolean;
}

export interface EnvCheckItem {
  item: string;
  ok: boolean;
  hint: string;
}

export interface EnvCheckResponse {
  all_ok: boolean;
  checks: EnvCheckItem[];
  storage: Record<string, number>;
  python_hint: string;
}
