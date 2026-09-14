"""统一日志配置。

目的：让组员在终端里看到一致的、带模块名的日志，
而不是满屏 print，出问题时无法定位是哪个 agent 挂的。
"""

from __future__ import annotations

import logging
import sys

from app.core.config import settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-28s | %(message)s"
_DATE_FORMAT = "%H:%M:%S"


def setup_logging() -> None:
    """在应用启动时调用一次。"""
    level = logging.DEBUG if settings.debug else logging.INFO

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # 第三方库日志太吵，压到 WARNING
    for noisy in ("httpx", "httpcore", "openai", "urllib3", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "日志已初始化 env=%s debug=%s llm_configured=%s",
        settings.env,
        settings.debug,
        settings.llm_configured,
    )
