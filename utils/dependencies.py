from redis import asyncio as aioredis

# 全局变量用于存储Redis连接池
redis = None


async def get_redis_connection():
    """依赖项函数，用于获取 Redis 连接."""
    global redis
    if redis is None:
        # 在第一次调用时初始化 Redis 连接
        redis = aioredis.from_url(
            "redis://localhost:6379/0",
            encoding="utf8",
            decode_responses=True,
        )
    return redis


async def close_redis_connection():
    """关闭 Redis 连接."""
    global redis
    if redis is not None:
        await redis.close()
        redis = None  # 重置为 None，以防再次尝试关闭
