"""
config.py - 统一配置中心
集中管理所有模型参数、路径、缓存配置等，避免各文件硬编码不一致
"""

from __future__ import annotations

import os
import logging
from typing import Optional
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class PathConfig:
    """路径相关配置"""
    def __init__(self, project_root: Optional[str] = None):
        if project_root is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(script_dir))
        self.PROJECT_ROOT = os.path.abspath(project_root)
        self.DATA_DIR = os.path.join(self.PROJECT_ROOT, "data")
        self.RULES_DIR = os.path.join(self.DATA_DIR, "rules")
        self.VECTOR_STORE_DIR = os.path.join(self.DATA_DIR, "vector_store")
        self.LOG_DIR = os.path.join(self.PROJECT_ROOT, "logs")
        self.PROMPTS_DIR = os.path.join(self.PROJECT_ROOT, "backend", "app", "prompts")
        self.TEST_CASES_PATH = os.path.join(self.DATA_DIR, "test_cases.json")
        self.EVAL_REPORT_PATH = os.path.join(self.DATA_DIR, "rag_eval_report.csv")

_PATH_CONFIG_SINGLETON: Optional[PathConfig] = None

def get_path_config(project_root: Optional[str] = None) -> PathConfig:
    """获取路径配置（支持自定义 project_root）"""
    global _PATH_CONFIG_SINGLETON
    if _PATH_CONFIG_SINGLETON is None or project_root is not None:
        _PATH_CONFIG_SINGLETON = PathConfig(project_root)
    return _PATH_CONFIG_SINGLETON

class _Settings(BaseSettings):
    """应用配置基类，支持从环境变量和 .env 文件加载"""
    _env_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
    model_config = SettingsConfigDict(env_file=_env_file_path, env_file_encoding="utf-8", extra="ignore")

class ModelConfig(_Settings):
    """模型相关配置"""
    LLM_MODEL: str = Field(default="qwen-max", description="通义千问模型名称")
    LLM_TEMPERATURE: float = Field(default=0.0, ge=0.0, le=1.0, description="LLM 温度")
    EMBEDDING_PROVIDER: str = Field(default="dashscope", description="嵌入模型提供商")
    EMBEDDING_MODEL: str = Field(default="text-embedding-v4", description="DashScope 嵌入模型")
    EMBEDDING_HF_MODEL: str = Field(
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        description="HuggingFace 嵌入模型",
    )
    EMBEDDING_HF_DEVICE: str = Field(default="cpu", description="HuggingFace 运行设备")
    EMBEDDING_HF_MIRROR: Optional[str] = Field(default=None, description="HuggingFace 镜像地址，例如 https://hf-mirror.com")
    EMBEDDING_HF_LOCAL_DIR: Optional[str] = Field(default=None, description="本地离线模型目录，优先于网络加载")
    RETRIEVER_TOP_K: int = Field(default=10, ge=1, le=50, description="粗召回数量")
    RERANK_ENABLED: bool = Field(default=True, description="是否启用重排")
    RERANK_MODEL: str = Field(default="qwen3-vl-rerank", description="重排模型")
    RERANK_TOP_N: int = Field(default=3, ge=1, le=10, description="重排后保留数量")
    RERANK_RETURN_DOCUMENTS: bool = True
    DASHSCOPE_API_KEY: str = Field(default="", description="DashScope API Key")

    @model_validator(mode="after")
    def check_api_key(self) -> "ModelConfig":
        required = os.getenv("DASHSCOPE_API_KEY_REQUIRED", "true").strip().lower()
        if required != "false":
            if not self.DASHSCOPE_API_KEY or self.DASHSCOPE_API_KEY == "your-dashscope-api-key-here":
                raise ValueError("DASHSCOPE_API_KEY 未配置或无效")
        return self

    def validate_api_key(self) -> bool:
        """检查 API Key 是否有效"""
        return bool(self.DASHSCOPE_API_KEY) and self.DASHSCOPE_API_KEY != "your-dashscope-api-key-here"

class CacheConfig(_Settings):
    """缓存相关配置"""
    CACHE_CAPACITY: int = Field(default=128, ge=0, description="缓存容量")
    CACHE_TTL_SECONDS: int = Field(default=3600, ge=0, description="缓存 TTL（秒）")

class RetryConfig(_Settings):
    """API 重试配置"""
    MAX_RETRIES: int = Field(default=3, ge=0, le=10, description="最大重试次数")
    RETRY_DELAY_SECONDS: float = Field(default=1.0, ge=0.0, description="重试间隔（秒）")

class ServerSecurityConfig(_Settings):
    """服务安全与限流配置"""
    API_TOKEN: Optional[str] = Field(default=None, description="Bearer Token，为空表示关闭鉴权")
    RATE_LIMIT_WINDOW_SECONDS: int = Field(default=60, ge=1, description="限流窗口（秒）")
    RATE_LIMIT_MAX_REQUESTS: int = Field(default=30, ge=1, description="窗口内最大请求数")

class ServerRuntimeConfig(_Settings):
    """服务运行配置"""
    HOST: str = Field(default="0.0.0.0", description="监听地址")
    PORT: int = Field(default=8000, ge=1, le=65535, description="监听端口")
    WORKERS: int = Field(default=1, ge=1, le=8, description="工作进程数")
    RELOAD: bool = Field(default=False, description="是否热重载")
    LOG_LEVEL: str = Field(default="INFO", description="日志级别")
    APP_TITLE: str = Field(default="ISSF 2026 规则问答助手", description="应用标题")
    APP_VERSION: str = Field(default="0.1.0", description="应用版本")

# 全局单例配置实例
MODEL_CONFIG = ModelConfig()
CACHE_CONFIG = CacheConfig()
RETRY_CONFIG = RetryConfig()
SECURITY_CONFIG = ServerSecurityConfig()
RUNTIME_CONFIG = ServerRuntimeConfig()