"""
速率限制器模块

使用滑动窗口算法的内存缓存实现。
适用于单实例部署，如需多实例部署可扩展为 Redis 实现。

特点：
- 异步安全（使用 asyncio.Lock）
- 自动清理过期数据
- 支持多种限制规则
- 低内存占用
"""

from asyncio import Lock
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class SlidingWindowRateLimiter:
    """
    滑动窗口速率限制器

    使用滑动窗口算法实现精确的速率限制。
    相比固定窗口算法，滑动窗口能避免边界突发问题。

    使用示例：
        limiter = SlidingWindowRateLimiter()

        # 检查是否允许请求
        allowed, remaining, reset = await limiter.is_allowed(
            key="login:192.168.1.1",
            max_requests=5,
            window_seconds=300
        )

        if not allowed:
            raise HTTPException(429, f"请求过于频繁，请 {reset} 秒后再试")
    """

    def __init__(self, cleanup_interval_minutes: int = 5):
        """
        初始化速率限制器

        Args:
            cleanup_interval_minutes: 清理过期数据的间隔（分钟）
        """
        # 缓存结构: {key: [timestamp1, timestamp2, ...]}
        self._cache: Dict[str, List[datetime]] = {}
        # 异步锁，确保线程安全
        self._lock = Lock()
        # 最后清理时间
        self._last_cleanup = datetime.now()
        # 清理间隔
        self._cleanup_interval = timedelta(minutes=cleanup_interval_minutes)

    async def is_allowed(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> Tuple[bool, int, int]:
        """
        检查是否允许请求

        Args:
            key: 限制键（如 "login:192.168.1.1" 或 "global:192.168.1.1"）
            max_requests: 时间窗口内最大请求数
            window_seconds: 时间窗口长度（秒）

        Returns:
            元组 (是否允许, 剩余请求数, 重置时间秒数)
        """
        async with self._lock:
            now = datetime.now()
            window_start = now - timedelta(seconds=window_seconds)

            # 定期清理过期数据
            if now - self._last_cleanup > self._cleanup_interval:
                await self._cleanup_expired(window_start)
                self._last_cleanup = now

            # 获取或初始化该 key 的记录
            if key not in self._cache:
                self._cache[key] = []

            # 清理该 key 的过期记录（窗口外的时间戳）
            self._cache[key] = [
                ts for ts in self._cache[key] if ts > window_start
            ]

            current_count = len(self._cache[key])
            remaining = max(0, max_requests - current_count)

            # 计算重置时间（最早记录过期的时间）
            if self._cache[key]:
                oldest = min(self._cache[key])
                reset_seconds = max(
                    0,
                    int((oldest + timedelta(seconds=window_seconds) - now).total_seconds())
                )
            else:
                reset_seconds = window_seconds

            # 检查是否超过限制
            if current_count >= max_requests:
                return False, 0, reset_seconds

            # 记录本次请求时间戳
            self._cache[key].append(now)
            return True, remaining - 1, reset_seconds

    async def get_count(self, key: str, window_seconds: int) -> int:
        """
        获取当前时间窗口内的请求数

        Args:
            key: 限制键
            window_seconds: 时间窗口长度（秒）

        Returns:
            当前窗口内的请求数
        """
        async with self._lock:
            now = datetime.now()
            window_start = now - timedelta(seconds=window_seconds)

            if key not in self._cache:
                return 0

            return len([ts for ts in self._cache[key] if ts > window_start])

    async def reset(self, key: str) -> bool:
        """
        重置指定 key 的计数

        Args:
            key: 要重置的限制键

        Returns:
            是否成功重置（key 存在则为 True）
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def reset_pattern(self, pattern: str) -> int:
        """
        重置匹配模式的所有 key

        Args:
            pattern: 键前缀（如 "login:" 会重置所有登录相关的限制）

        Returns:
            重置的 key 数量
        """
        async with self._lock:
            keys_to_delete = [
                key for key in self._cache.keys() if key.startswith(pattern)
            ]
            for key in keys_to_delete:
                del self._cache[key]
            return len(keys_to_delete)

    async def _cleanup_expired(self, cutoff: datetime) -> None:
        """
        清理所有过期记录

        Args:
            cutoff: 截止时间，早于此时间的记录将被清理
        """
        keys_to_delete = []

        for key, timestamps in self._cache.items():
            # 过滤出有效的时间戳
            valid = [ts for ts in timestamps if ts > cutoff]
            if valid:
                self._cache[key] = valid
            else:
                keys_to_delete.append(key)

        # 删除空记录
        for key in keys_to_delete:
            del self._cache[key]

        if keys_to_delete:
            logger.debug(f"清理了 {len(keys_to_delete)} 个过期的速率限制记录")

    async def get_stats(self) -> dict:
        """
        获取速率限制器的统计信息

        Returns:
            包含统计信息的字典
        """
        async with self._lock:
            total_keys = len(self._cache)
            total_records = sum(len(v) for v in self._cache.values())

            # 按前缀分组统计
            prefix_stats = {}
            for key in self._cache.keys():
                prefix = key.split(":")[0] if ":" in key else key
                prefix_stats[prefix] = prefix_stats.get(prefix, 0) + 1

            return {
                "total_keys": total_keys,
                "total_records": total_records,
                "prefix_stats": prefix_stats,
                "last_cleanup": self._last_cleanup.isoformat(),
            }


# 全局速率限制器单例
rate_limiter = SlidingWindowRateLimiter()
