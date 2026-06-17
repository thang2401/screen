"""
Redis Cache cho real-time data.
Tăng tốc độ truy xuất dữ liệu, giảm tải database.
"""

import json
import time
import logging
from typing import Optional, Dict, Any, List
from datetime import timedelta

logger = logging.getLogger(__name__)

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available. Using in-memory cache.")


class InMemoryCache:
    """In-memory cache fallback khi không có Redis."""

    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}

    async def get(self, key: str) -> Optional[Any]:
        if key in self._data:
            if key in self._expiry and time.time() > self._expiry[key]:
                del self._data[key]
                del self._expiry[key]
                return None
            return self._data[key]
        return None

    async def set(self, key: str, value: Any, expire: int = 300):
        self._data[key] = value
        if expire > 0:
            self._expiry[key] = time.time() + expire

    async def delete(self, key: str):
        self._data.pop(key, None)
        self._expiry.pop(key, None)

    async def exists(self, key: str) -> bool:
        return key in self._data

    async def keys(self, pattern: str = "*") -> List[str]:
        return [k for k in self._data.keys() if pattern == "*" or pattern in k]


class RedisCache:
    """
    Redis Cache Manager với:
    - Async Redis client
    - Connection pool
    - Automatic serialization
    - TTL management
    - Pub/Sub cho real-time events
    """

    def __init__(self, url: str = "redis://localhost:6379/0"):
        self.url = url
        self.client = None
        self.pubsub = None
        self._use_redis = REDIS_AVAILABLE

        if not self._use_redis:
            self._memory_cache = InMemoryCache()
            logger.info("Using in-memory cache fallback")

    async def initialize(self):
        """Khởi tạo Redis connection."""
        if not self._use_redis:
            return

        try:
            self.client = aioredis.from_url(
                self.url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=10,
            )
            await self.client.ping()
            self.pubsub = self.client.pubsub()
            logger.info(f"Redis cache initialized: {self.url}")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Using in-memory cache.")
            self._use_redis = False
            self._memory_cache = InMemoryCache()

    async def get(self, key: str) -> Optional[Any]:
        """Lấy giá trị từ cache."""
        if not self._use_redis:
            return await self._memory_cache.get(key)

        try:
            data = await self.client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None

    async def set(self, key: str, value: Any, expire: int = 300):
        """Lưu giá trị vào cache."""
        if not self._use_redis:
            return await self._memory_cache.set(key, value, expire)

        try:
            await self.client.setex(key, expire, json.dumps(value))
        except Exception as e:
            logger.error(f"Redis set error: {e}")

    async def delete(self, key: str):
        """Xóa key khỏi cache."""
        if not self._use_redis:
            return await self._memory_cache.delete(key)

        try:
            await self.client.delete(key)
        except Exception as e:
            logger.error(f"Redis delete error: {e}")

    async def exists(self, key: str) -> bool:
        """Kiểm tra key tồn tại."""
        if not self._use_redis:
            return await self._memory_cache.exists(key)

        try:
            return await self.client.exists(key) > 0
        except:
            return False

    # ===== Specific Cache Operations =====

    async def cache_client_info(self, client_id: str, info: dict):
        """Cache thông tin client."""
        await self.set(f"client:{client_id}", info, expire=60)

    async def get_cached_client(self, client_id: str) -> Optional[dict]:
        """Lấy thông tin client từ cache."""
        return await self.get(f"client:{client_id}")

    async def cache_frame(self, client_id: str, frame_data: bytes,
                          expire: int = 5):
        """Cache frame gần nhất của client (dùng cho replay)."""
        key = f"frame:{client_id}:latest"
        if not self._use_redis:
            await self._memory_cache.set(key, frame_data, expire)
        else:
            try:
                await self.client.setex(key, expire, frame_data)
            except:
                pass

    async def get_cached_frame(self, client_id: str) -> Optional[bytes]:
        """Lấy frame gần nhất từ cache."""
        if not self._use_redis:
            return await self._memory_cache.get(f"frame:{client_id}:latest")
        try:
            return await self.client.get(f"frame:{client_id}:latest")
        except:
            return None

    # ===== Pub/Sub =====

    async def publish(self, channel: str, message: dict):
        """Publish message lên channel."""
        if not self._use_redis:
            return

        try:
            await self.client.publish(channel, json.dumps(message))
        except Exception as e:
            logger.error(f"Redis publish error: {e}")

    async def subscribe(self, channel: str):
        """Subscribe vào channel."""
        if not self._use_redis:
            return

        try:
            await self.pubsub.subscribe(channel)
        except Exception as e:
            logger.error(f"Redis subscribe error: {e}")

    async def get_message(self, timeout: float = 0.1) -> Optional[dict]:
        """Lấy message từ subscribed channels."""
        if not self._use_redis:
            return None

        try:
            message = await self.pubsub.get_message(
                timeout=timeout, ignore_subscribe_messages=True
            )
            if message and message['type'] == 'message':
                return json.loads(message['data'])
            return None
        except:
            return None

    # ===== Cache Management =====

    async def flush(self):
        """Xóa toàn bộ cache."""
        if not self._use_redis:
            self._memory_cache = InMemoryCache()
            return

        try:
            await self.client.flushdb()
            logger.info("Cache flushed")
        except Exception as e:
            logger.error(f"Redis flush error: {e}")

    async def get_stats(self) -> dict:
        """Lấy thống kê cache."""
        if not self._use_redis:
            return {'type': 'memory', 'keys': len(self._memory_cache._data)}

        try:
            info = await self.client.info()
            return {
                'type': 'redis',
                'used_memory': info.get('used_memory_human', 'N/A'),
                'connected_clients': info.get('connected_clients', 0),
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
                'uptime_days': info.get('uptime_in_days', 0),
            }
        except:
            return {'type': 'redis', 'error': 'connection failed'}

    async def close(self):
        """Đóng Redis connection."""
        if self.client:
            await self.client.close()
            logger.info("Redis connection closed")