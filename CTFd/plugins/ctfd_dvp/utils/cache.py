"""
Redis-клиент и распределённая блокировка.
"""

import redis
import os
import time

redis_client = None


def get_redis():
    global redis_client

    if redis_client is not None:
        return redis_client

    redis_url = os.getenv("REDIS_URL")

    if not redis_url:
        raise RuntimeError("[DVP] REDIS_URL is not set")

    client = redis.from_url(redis_url, decode_responses=True)
    client.ping()
    redis_client = client
    print(f"[DVP] Redis connected: {redis_url}")

    return redis_client


def acquire_lock(lock_name="dvp:launch_lock", timeout=10):
    r = get_redis()
    if not r:
        return True
    return bool(r.set(f"dvp:lock:{lock_name}", str(time.time()), nx=True, ex=timeout))


def release_lock(lock_name="dvp:launch_lock"):
    r = get_redis()
    if r:
        r.delete(f"dvp:lock:{lock_name}")