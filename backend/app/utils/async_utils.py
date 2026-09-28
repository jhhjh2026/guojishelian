"""
async_utils.py - 异步兼容工具层
提供与现有同步重试/重排逻辑等价的异步接口，用于后续 Web 服务改造。
当前为最小可用版本，不改动现有同步链路。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine, Dict, List

from langchain_core.documents import Document
from .retry_utils import retry_call as _sync_retry_call

logger = logging.getLogger("async_utils")

async def _run_sync_in_executor(func: Callable, *args: Any, **kwargs: Any) -> Any:
    """在线程池中运行同步函数，避免阻塞事件循环"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: _sync_retry_call(func, *args, **kwargs))

async def async_retry_call(func: Callable, *args: Any, **kwargs: Any) -> Any:
    """异步重试调用：底层复用现有同步 retry_call，避免重复实现退避逻辑"""
    return await _run_sync_in_executor(func, *args, **kwargs)

async def async_rerank_documents(
        query: str,
        documents: List[Document],
        api_key: str,
        model: str = "gte-rerank-v2",
        top_n: int = 3,
        return_documents: bool = True,
        max_retries: int = 3,
        retry_delay: float = 1.0,
) -> List[Document]:
    """异步重排：在后台线程中执行同步重排，避免阻塞 asyncio 事件循环"""
    from .reranker import rerank_documents

    def _call() -> List[Document]:
        return rerank_documents(
            query=query,
            documents=documents,
            api_key=api_key,
            model=model,
            top_n=top_n,
            return_documents=return_documents,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )

    return await _run_sync_in_executor(_call)

__all__ = [
    "async_retry_call",
    "async_rerank_documents",
]