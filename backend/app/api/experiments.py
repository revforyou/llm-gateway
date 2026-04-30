from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.core.auth import verify_api_key_dep
from app.core.db import get_db
from app.experiments.engine import create_experiment, recompute_stats
from app.models.schemas import ApiResponse

router = APIRouter(prefix="/v1/experiments", tags=["experiments"])


class CreateExperimentRequest(BaseModel):
    name: str
    hypothesis: str = ""
    variant_a: dict
    variant_b: dict
    traffic_split: float = 0.5
    min_sample_size: int = 100
    max_sample_size: int = 2000


@router.post("", response_model=ApiResponse)
async def create(body: CreateExperimentRequest, auth: dict = Depends(verify_api_key_dep)):
    exp = create_experiment(
        team_id=auth["team_id"],
        name=body.name,
        hypothesis=body.hypothesis,
        variant_a=body.variant_a,
        variant_b=body.variant_b,
        traffic_split=body.traffic_split,
        min_sample_size=body.min_sample_size,
        max_sample_size=body.max_sample_size,
    )
    return ApiResponse(data=exp)


@router.get("", response_model=ApiResponse)
async def list_experiments(auth: dict = Depends(verify_api_key_dep)):
    db = get_db()
    rows = (
        db.table("experiments")
        .select("*")
        .eq("team_id", auth["team_id"])
        .order("started_at", desc=True)
        .execute()
    ).data or []
    return ApiResponse(data=rows)


@router.get("/{experiment_id}/results", response_model=ApiResponse)
async def results(experiment_id: str, auth: dict = Depends(verify_api_key_dep)):
    stats = recompute_stats(experiment_id)
    return ApiResponse(data=stats)


@router.post("/{experiment_id}/conclude", response_model=ApiResponse)
async def conclude(experiment_id: str, auth: dict = Depends(verify_api_key_dep)):
    db = get_db()
    db.table("experiments").update({
        "status": "aborted",
        "concluded_at": "now()",
    }).eq("id", experiment_id).eq("team_id", auth["team_id"]).execute()
    return ApiResponse(data={"status": "aborted"})
