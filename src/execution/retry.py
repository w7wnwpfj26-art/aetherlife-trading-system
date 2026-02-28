"""
下单/撤单重试模块
指数退避 + 最大重试次数，防止因网络抖动导致指令丢失
"""

import asyncio
import logging
from typing import Any, Callable, Awaitable, Tuple, Type

logger = logging.getLogger(__name__)


async def retry_async(
    func: Callable[..., Awaitable[Any]],
    *args,
    max_retries: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 10.0,
    backoff_factor: float = 2.0,
    retriable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    **kwargs,
) -> Any:
    """
    通用异步重试（指数退避）

    :param func:               待重试的异步函数
    :param max_retries:        最大重试次数（不含首次调用）
    :param base_delay:         首次重试等待（秒）
    :param max_delay:          最大等待上限（秒）
    :param backoff_factor:     每次等待时间乘数
    :param retriable_exceptions: 可重试异常类型
    :return:                   函数返回值
    :raises:                   最后一次失败的异常
    """
    delay = base_delay
    last_exc: Exception = RuntimeError("未执行")

    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except retriable_exceptions as exc:
            last_exc = exc
            if attempt >= max_retries:
                logger.error(
                    "重试已达上限 %d 次，放弃: %s — %s",
                    max_retries, func.__name__, exc,
                )
                raise
            wait = min(delay, max_delay)
            logger.warning(
                "调用 %s 失败（第 %d/%d 次）: %s，%.1f 秒后重试",
                func.__name__, attempt + 1, max_retries, exc, wait,
            )
            await asyncio.sleep(wait)
            delay = min(delay * backoff_factor, max_delay)

    raise last_exc


async def cancel_with_retry(
    client,
    symbol: str,
    order_id: str,
    max_retries: int = 3,
) -> dict:
    """带重试的撤单"""
    return await retry_async(
        client.cancel_order,
        symbol,
        order_id,
        max_retries=max_retries,
        base_delay=0.5,
        max_delay=5.0,
    )


async def place_order_with_retry(
    client,
    max_retries: int = 3,
    **order_kwargs,
) -> dict:
    """带重试的下单"""
    return await retry_async(
        client.place_order,
        max_retries=max_retries,
        base_delay=0.3,
        max_delay=5.0,
        **order_kwargs,
    )
