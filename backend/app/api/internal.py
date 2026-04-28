from fastapi import APIRouter, Header, HTTPException, status
from app.core.config import settings
from app.core.db import get_db
from app.core.cache import get_redis
from app.models.schemas import ApiResponse

router = APIRouter(prefix="/v1/internal", tags=["internal"])


def _require_cron(x_cron_secret: str = Header(...)):
    if x_cron_secret != settings.internal_cron_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


@router.post("/keep-warm", response_model=ApiResponse)
async def keep_warm(x_cron_secret: str = Header(...)) -> ApiResponse:
    _require_cron(x_cron_secret)

    db_ok = False
    redis_ok = False

    try:
        get_db().table("teams").select("id").limit(1).execute()
        db_ok = True
    except Exception:
        pass

    try:
        get_redis().ping()
        redis_ok = True
    except Exception:
        pass

    return ApiResponse(data={"db": db_ok, "redis": redis_ok})


@router.post("/run-drift", response_model=ApiResponse)
async def run_drift(x_cron_secret: str = Header(...)) -> ApiResponse:
    _require_cron(x_cron_secret)
    # Drift module imported here to avoid circular imports at startup
    from app.eval.drift import run_drift_check
    await run_drift_check()
    return ApiResponse(data={"status": "drift check complete"})
