"""
统一日志模块
控制台彩色输出 + 可选文件轮转，便于排查与接入监控
"""

import logging
import sys
import os
from logging.handlers import RotatingFileHandler
from typing import Optional

_loggers: dict = {}   # name → Logger，支持多命名 logger 共存


def get_logger(
    name: str = "trading",
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,   # 默认单文件最大 10 MB
    backup_count: int = 5,               # 最多保留 5 个历史文件
) -> logging.Logger:
    """
    获取或创建统一 logger。

    :param name:         logger 名称，相同名称复用同一实例
    :param level:        日志级别
    :param log_file:     日志文件路径；为 None 则只输出到控制台
    :param max_bytes:    单个日志文件最大字节数（触发轮转）
    :param backup_count: 保留的历史日志文件数量
    """
    global _loggers
    if name in _loggers:
        return _loggers[name]

    log = logging.getLogger(name)
    log.setLevel(level)
    log.propagate = False   # 避免被 root logger 重复处理

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ── 控制台 Handler ──────────────────────────────
    if not any(isinstance(h, logging.StreamHandler) and h.stream is sys.stdout
               for h in log.handlers):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(fmt)
        console_handler.setLevel(level)
        log.addHandler(console_handler)

    # ── 文件 Handler（轮转）──────────────────────────
    if log_file and not any(isinstance(h, RotatingFileHandler) for h in log.handlers):
        try:
            log_dir = os.path.dirname(log_file)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setFormatter(fmt)
            file_handler.setLevel(level)
            log.addHandler(file_handler)
        except OSError as e:
            log.warning("无法创建日志文件 %s: %s，仅使用控制台输出", log_file, e)

    _loggers[name] = log
    return log


def set_level(name: str = "trading", level: int = logging.DEBUG):
    """动态调整指定 logger 的日志级别（无需重启）"""
    log = logging.getLogger(name)
    log.setLevel(level)
    for h in log.handlers:
        h.setLevel(level)


def log_exception(log: logging.Logger, msg: str = "异常"):
    """记录当前异常与完整 traceback"""
    log.exception(msg)
