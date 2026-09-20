# 个性化资源生成与学习多智能体系统

> 软件工程课程项目 · 脚手架仓库
> 需求：对话式学习画像（≥6 维度）· 多智能体协同生成（≥5 类资源）· 个性化学习路径规划

本文档是**全组唯一入口**。任何环境、协作、开发上的问题，先在这里找答案。

---

## 一、5 分钟跑起来（有经验的同学看这里）

```powershell
# 1. 初始化（会自动建 conda 环境、装依赖、生成 .env）
pwsh -File scripts/setup.ps1

# 2. 填入 LLM API Key
notepad backend\.env        # 把 LLM_API_KEY=sk-在这里填你的真实Key 改成真实 Key

# 3. 启动前后端
pwsh -File scripts/dev.ps1
```

| 地址 | 用途 |
|---|---|
| http://127.0.0.1:8000/docs | 后端 API 文档（答辩演示用） |
| http://127.0.0.1:5173 | 前端页面 |
| http://127.0.0.1:8000/api/env-check | 环境自检（排查问题先看这个） |

**零基础同学请直接看 👉 [`docs/组员环境安装手册.md`](docs/组员环境安装手册.md)**

---

## 二、技术栈与选型理由

| 层 | 选择 | 版本 | 为什么 |
|---|---|---|---|
| 语言 | Python | **3.13** | 老师指定；已刻意避开 3.13 上装不动的本地推理库 |
| 环境 | Miniconda | 最新 | 隔离依赖，避免全组版本互相污染 |
| Web | FastAPI + Uvicorn | `>=0.115` | 自动生成 API 文档，答辩演示直接可用 |
| 多智能体 | **LangGraph** | `>=1.2` | 状态机式的可控协作，比 CrewAI 更适合"必须讲清协作流程"的需求 |
| LLM 接入 | langchain-openai | `>=1.6` | OpenAI 兼容协议，换供应商只改 `.env` |
| 前端 | React + TypeScript + Vite | React 18 / Vite 6 | 类型安全 + 秒级热更新 |
| 包管理 | pnpm | `>=9` | 比 npm 快且磁盘占用低，锁文件更严格 |
| 数据库 | SQLite（开发） | — | 答辩前换 PostgreSQL，只改一处 DSN |

### ⚠️ 关键架构决策：为什么全程走 API，不做本地模型

需求里的多模态生成（视频/动画）很容易让人想到本地部署模型，但基于 **Python 3.13** 的现实：

- `torch` / `sentence-transformers` / `faiss` 在 Windows + 3.13 上**缺少预编译 wheel**，装它要现场编译，小白组员几乎必然卡死
- 本地 7B 模型**扛不住多智能体复杂推理**（一个流程要调十几次 LLM）

因此本项目统一策略：**所有模型能力走远程 API**。
代价是要花点钱，收益是全组环境搭建从"两天"降到"十分钟"。

---

## 三、目录结构

> 仓库根目录即项目根目录（没有多余的嵌套层）。

```
textGit/
├── backend/                     后端
│   ├── app/
│   │   ├── main.py              FastAPI 入口（含 CORS、生命周期）
│   │   ├── core/
│   │   │   ├── config.py        ★ 所有配置集中在这里（唯一真相源）
│   │   │   ├── llm.py           LLM 客户端工厂（含重试）
│   │   │   ├── logging.py       统一日志
│   │   │   └── schemas.py       ★ 领域模型 + API 契约（改它要同步前端）
│   │   ├── agents/              多智能体（需求核心）
│   │   │   ├── base.py          BaseAgent + AgentContext（黑板模式）
│   │   │   ├── profile_agent.py 画像智能体（需求 1）
│   │   │   ├── resource_agents.py 6 个资源智能体 + 大纲 + 路径规划
│   │   │   └── __init__.py      ★ 智能体注册表
│   │   ├── graph/
│   │   │   └── orchestrator.py  ★ 多智能体调度（并行 + 失败隔离）
│   │   ├── api/                 HTTP 接口
│   │   │   ├── profile.py       画像接口（需求 1）
│   │   │   ├── resources.py     资源生成接口（需求 2）
│   │   │   ├── path.py          学习路径接口（需求 3）
│   │   │   └── system.py        健康检查 + 环境自检
│   │   └── store/memory.py      存储层（当前内存版，预留换 DB 的接缝）
│   ├── tests/test_basic.py      基础测试（不需要 API Key）
│   ├── requirements.txt         ★ 后端依赖唯一真相源
│   ├── requirements-optional.txt 可选依赖（按角色装）
│   ├── pyproject.toml           ★ ruff + pytest 统一配置
│   └── .env.example             ★ 环境变量模板
│
├── frontend/                    前端
│   ├── src/
│   │   ├── api/client.ts        ★ 唯一网络入口（错误统一转中文）
│   │   ├── types/api.ts         ★ 必须与后端 schemas.py 对齐
│   │   ├── App.tsx              自检页（后续替换为业务页面）
│   │   └── main.tsx
│   ├── package.json             ★ 前端依赖唯一真相源
│   ├── vite.config.ts           ★ 含 /api → 8000 代理
│   └── tsconfig*.json           ★ 严格模式 TS 配置
│
├── scripts/
│   ├── setup.ps1                ★ 一键初始化
│   ├── setup.bat                双击即可运行版本
│   └── dev.ps1                  ★ 一键启动前后端
│
├── docs/
│   ├── 组员环境安装手册.md       ★ 零基础必看
│   ├── 工具链清单.md            必须 / 可选 / 加分项 分层说明
│   └── 协作规范.md              ★ Git 分支、提交、评审约定
│
├── .editorconfig                ★ 统一缩进与行尾
├── .gitattributes               ★ 强制 LF，杜绝跨平台假 diff
├── .gitignore                   ★ 屏蔽 .env / 缓存 / 生成物
└── .vscode/                     推荐插件 + 统一编辑器设置
```

★ = 需要全组对齐的关键文件

---

## 四、需求 → 实现对应表

| 老师的要求 | 实现位置 | 达标情况 |
|---|---|---|
| 1. 对话式画像，≥6 维度，随学随新 | `agents/profile_agent.py` | ✅ 定义了 8 个维度；`StudentProfile.version` 支持增量更新 |
| 2. 多智能体架构 | `agents/` + `graph/orchestrator.py` | ✅ 8 个角色智能体 + 黑板协作 + 并行调度 + 失败隔离 |
| 2. ≥5 类资源生成 | `agents/resource_agents.py` | ✅ 定义了 6 类，每类独立智能体 |
| 3. 个性化学习路径 | `api/path.py` + `PathPlannerAgent` | ✅ LLM 生成 + 确定性兜底双通道 |
| 3. 精准资源推送 | `PathStep.resource_ids` 关联 | ✅ 路径步骤直接绑定资源 id |
| 4. 智能辅导（加分） | **待认领** | ⬜ 未实现 |
| 5. 学习效果评估（加分） | **待认领** | ⬜ 未实现 |

---

## 五、协作铁律（违反会导致全组返工）

1. **禁止在 `base` 环境装依赖。** 必须在 `learnagent` 环境里操作。
2. **禁止手改 `.env` 后提交。** `.env` 已在 `.gitignore` 里，只提交 `.env.example`。
3. **禁止 `pip install` 未经商量的包。** 要加依赖 → 改 `requirements.txt` 并在群里说一声。
4. **改 `backend/app/core/schemas.py` 必须同时改 `frontend/src/types/api.ts`。** 否则前端静默拿到 `undefined`。
5. **不要把生成的资源（`storage/`）提交上去。** 体积大且可重新生成。
6. **提交前跑一遍** `ruff check .` 和 `pytest`（详见协作规范）。

---

## 六、常见问题

<details>
<summary><b>启动后端报 <code>ModuleNotFoundError</code></b></summary>

99% 是没激活环境。执行 `conda activate learnagent` 再启动。
若确认已激活仍报错，跑 `pip install -r backend/requirements.txt`。
</details>

<details>
<summary><b>接口返回 503 "未检测到 LLM_API_KEY"</b></summary>

`backend/.env` 里的 Key 没填或填错。注意：
- 不要有引号包裹
- 不要有多余空格
- 文件必须叫 `.env`（不是 `.env.txt`，Windows 默认隐藏扩展名容易踩）
</details>

<details>
<summary><b>前端报"无法连接后端"</b></summary>

后端没起。确认 `backend` 目录下执行了 `uvicorn app.main:app --reload --port 8000`。
若后端已在跑，检查 8000 端口是否被占用：`netstat -ano | findstr :8000`
</details>

<details>
<summary><b>生成任务一直是"生成中"</b></summary>

5 类资源要调十几次 LLM，正常需要 30~90 秒。看后端窗口日志确认进度。
超过 3 分钟仍无结果，看日志里哪个智能体报错 —— 单点失败不会阻塞其它资源。
</details>

<details>
<summary><b>pip 安装极慢或超时</b></summary>

用国内镜像：
```powershell
pip install -r backend/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```
</details>

<details>
<summary><b>Git 显示大量文件被修改但内容没变</b></summary>

行尾符问题（Windows CRLF vs LF）。确认 `.gitattributes` 存在且已提交，然后：
```powershell
git add --renormalize .
```
</details>

---

## 七、当前进度

- [x] 脚手架搭建（配置文件、依赖锁定、一键脚本）
- [x] 多智能体骨架（8 个角色智能体 + 编排器）
- [x] 三大核心接口（画像 / 资源生成 / 学习路径）
- [x] 基础测试与环境自检
- [ ] 前端业务界面
- [ ] 智能辅导（加分项 4）
- [ ] 学习效果评估（加分项 5）
- [ ] 数据库持久化（替换内存存储）
- [ ] 部署到服务器

> 分工与认领见 `docs/协作规范.md`
