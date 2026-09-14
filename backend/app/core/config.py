"""应用配置：所有可调参数集中在这里，禁止散落在代码各处的魔法字符串。

组员注意：任何"密钥 / 地址 / 模型名"都必须走这里，
不要在业务代码里写 os.getenv 或硬编码字符串。
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """从 .env 读取的运行时配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- 基础 ----
    app_name: str = "个性化资源生成与学习多智能体系统"
    env: Literal["dev", "test", "prod"] = "dev"
    debug: bool = True
    api_prefix: str = "/api"

    # ---- LLM（OpenAI 兼容协议，可换 DeepSeek / 通义 / OpenAI）----
    # 换供应商只需要改这三项，代码零改动
    llm_api_key: str = Field(default="", description="LLM API Key")
    llm_base_url: str = Field(
        default="https://api.deepseek.com/v1",
        description="OpenAI 兼容的 base_url",
    )
    llm_model: str = Field(default="deepseek-chat", description="主对话/推理模型")
    llm_temperature: float = 0.3

    # ---- Embedding（远程 API，避免本地 torch 依赖）----
    embedding_api_key: str = ""
    embedding_base_url: str = "https://api.deepseek.com/v1"
    embedding_model: str = "text-embedding-3-small"

    # ---- 多模态生成（可选，未配置则自动降级）----
    image_api_key: str = ""
    image_api_base_url: str = ""
    video_api_key: str = ""
    video_api_base_url: str = ""

    # ---- 数据库 ----
    database_url: str = "sqlite+aiosqlite:///./storage/learnagent.db"

    # ---- 前端联调 ----
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ---- 生成任务 ----
    max_concurrent_agents: int = 4
    agent_timeout_seconds: int = 180
    storage_dir: str = "./storage"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origin_list(self) -> list[str]:
        """把逗号分隔的字符串转成列表，供 CORSMiddleware 使用。"""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def llm_configured(self) -> bool:
        """是否已配置 LLM。未配置时接口返回友好提示而不是 500。"""
        return bool(self.llm_api_key)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def multimodal_enabled(self) -> bool:
        """多模态能力是否可用；不可用时视频类资源自动降级为图文。"""
        return bool(self.image_api_key or self.video_api_key)


@lru_cache
def get_settings() -> Settings:
    """单例配置。用 lru_cache 保证全应用只解析一次 .env。"""
    return Settings()


settings = get_settings()
