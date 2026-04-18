"""
Работа с Redis для кэширования состояния окружений.
"""

import redis
from flask import current_app


def get_redis_client():
    """
    Создаёт и возвращает клиент Redis.
    Использует REDIS_URL из конфигурации CTFd.
    """
    redis_url = current_app.config.get("REDIS_URL", "redis://localhost:6379")
    return redis.from_url(redis_url, decode_responses=True)


# Глобальный экземпляр
redis_client = get_redis_client()