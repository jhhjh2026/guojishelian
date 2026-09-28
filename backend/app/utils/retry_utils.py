"""
retry_utils.py - 重试工具
为不稳定的 API 调用（如 DashScope）提供带退避的重试机制
"""

import time
import logging
import functools
from typing import Callable, Any, Tuple, Type

logger = logging.getLogger("retry_utils")

def retry_call(
        func: Callable,
        *args,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        backoff_factor: float = 2.0,
        retry_exceptions: Tuple[Type[Exception], ...] = (Exception,),
        **kwargs
) -> Any:
    """
    同步函数重试调用
    """
    last_exception = None
    delay = retry_delay

    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except retry_exceptions as e:
            last_exception = e
            if attempt < max_retries:
                logger.warning(
                    f"[重试 {attempt + 1}/{max_retries}] {func.__name__} 调用失败: {e}, "
                    f"{delay:.1f}s 后重试..."
                )
                time.sleep(delay)
                delay *= backoff_factor
            else:
                logger.error(
                    f"[重试耗尽] {func.__name__} 在 {max_retries + 1} 次尝试后仍失败: {e}"
                )

    raise last_exception

def with_retry(
        max_retries: int = 3,
        retry_delay: float = 1.0,
        backoff_factor: float = 2.0,
        retry_exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> Callable:
    """装饰器版本的重试工具"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            return retry_call(
                func,
                *args,
                max_retries=max_retries,
                retry_delay=retry_delay,
                backoff_factor=backoff_factor,
                retry_exceptions=retry_exceptions,
                **kwargs
            )
        return wrapper
    return decorator