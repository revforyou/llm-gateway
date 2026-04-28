import json
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.db import get_db
from app.core.security import verify_key
from app.core.cache import get_redis

bearer = HTTPBearer()


async def verify_api_key_dep(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> dict:
    token = credentials.credentials
    prefix = token[:12]

    redis = get_redis()
    cache_key = f"auth:{prefix}"
    cached = redis.get(cache_key)
    if cached:
        return json.loads(cached)

    db = get_db()
    result = (
        db.table("api_keys")
        .select("id, team_id, key_hash, revoked_at")
        .eq("key_prefix", prefix)
        .single()
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    row = result.data
    if row.get("revoked_at"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key revoked")

    if not verify_key(token, row["key_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    db.table("api_keys").update({"last_used_at": "now()"}).eq("id", row["id"]).execute()

    payload = {"team_id": row["team_id"], "key_id": row["id"]}
    redis.setex(cache_key, 60, json.dumps(payload))
    return payload
