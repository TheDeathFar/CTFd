import redis
import os

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