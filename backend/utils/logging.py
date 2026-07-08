from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


# 日志目录:env CLIPSAY_LOG_DIR(由 Electron 主进程注入至 userData/logs)
# 回退到 <project>/_dev/logs,仅供开发使用,不污染仓库
_DEFAULT_LOG_DIR = Path(__file__).resolve().parents[2] / "_dev" / "logs"
LOG_DIR = Path(os.environ.get("CLIPSAY_LOG_DIR") or _DEFAULT_LOG_DIR)
LOG_DIR.mkdir(parents=True, exist_ok=True)


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(level)

    # 日志写入按天分文件,10MB 轮转,保留 14 份
    date_today = __import__("datetime").date.today().isoformat()
    file_handler = RotatingFileHandler(
        filename=LOG_DIR / f"backend-{date_today}.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=14,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(file_handler)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    ))
    logger.addHandler(stderr_handler)

    return logger
