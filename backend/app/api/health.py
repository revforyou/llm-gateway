from fastapi import APIRouter
from app.core.db import get_db
from app.core.cache import get_redis
from app.models.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    db_status = "ok"
    redis_status = "ok"

    try:
        get_db().table("teams").select("id").limit(1).execute()
    except Exception:
        db_status = "error"

    try:
        get_redis().ping()
    except Exception:
        redis_status = "error"

    return HealthResponse(status="ok", db=db_status, redis=redis_status)
