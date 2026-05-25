import json
import os
from fastapi import APIRouter
from app.core.db import get_db
from app.core.cache import get_redis
from app.models.schemas import HealthResponse

router = APIRouter()

_METRICS_PATH = os.path.join(os.path.dirname(__file__), "../gateway/classifier_metrics.json")


def _load_classifier_metrics() -> dict | None:
    try:
        with open(_METRICS_PATH) as f:
            return json.load(f)
    except Exception:
        return None


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

    return HealthResponse(
        status="ok",
        db=db_status,
        redis=redis_status,
        classifier=_load_classifier_metrics(),
    )
