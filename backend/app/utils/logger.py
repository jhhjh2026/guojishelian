"""
logger.py - 统一日志配置工具
"""

import os
import time
import logging
from typing import Tuple

def setup_logging(
        log_name: str = "issf_rag",
        log_dir: str = None,
        level: int = logging.INFO,
        project_root: str = None,
        json: bool = False,
) -> Tuple[logging.Logger, str]:
    """统一日志初始化"""
    if log_dir is None:
        if project_root is None:
            script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            project_root = os.path.dirname(script_dir)
        log_dir = os.path.join(project_root, "logs")

    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{log_name}_{time.strftime('%Y%m%d')}.log")

    logger = logging.getLogger(log_name)
    logger.setLevel(level)
    logger.handlers.clear()
    logger.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    if json:
        try:
            import json as _json
            json_file = os.path.join(log_dir, f"{log_name}_{time.strftime('%Y%m%d')}.jsonl")
            jh = logging.FileHandler(json_file, encoding="utf-8")
            jh.setLevel(level)
            jh.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(jh)
            logger.info(_json.dumps({"event": "logging_initialized", "log_file": log_file, "json_file": json_file}, ensure_ascii=False))
        except Exception:
            pass

    return logger, log_file