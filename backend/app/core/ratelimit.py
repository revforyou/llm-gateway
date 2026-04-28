import time
from fastapi import HTTPException, status
from app.core.cache import get_redis


def check_rate_limit(key_id: str) -> None:
    redis = get_redis()
    now = int(time.time())

    minute_key = f"rl:min:{key_id}:{now // 60}"
    hour_key = f"rl:hr:{key_id}:{now // 3600}"

    pipe = redis.pipeline()
    pipe.incr(minute_key)
    pipe.expire(minute_key, 90)
    pipe.incr(hour_key)
    pipe.expire(hour_key, 7200)
    results = pipe.execute()

    minute_count = results[0]
    hour_count = results[2]

    if minute_count > 60:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded: 60 requests/minute",
            headers={"X-RateLimit-Remaining": "0", "Retry-After": "60"},
        )
    if hour_count > 1000:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded: 1000 requests/hour",
            headers={"X-RateLimit-Remaining": "0", "Retry-After": "3600"},
        )
