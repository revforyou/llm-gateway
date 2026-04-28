from fastapi import APIRouter, Depends
from app.core.auth import verify_api_key_dep
from app.core.db import get_db
from app.models.schemas import ApiResponse

router = APIRouter(prefix="/v1/metrics", tags=["metrics"])


@router.get("/overview", response_model=ApiResponse)
async def overview(auth: dict = Depends(verify_api_key_dep)) -> ApiResponse:
    db = get_db()
    team_id = auth["team_id"]

    requests = (
        db.table("requests")
        .select("id, cost_usd, latency_ms, gateway_overhead_ms")
        .eq("team_id", team_id)
        .gte("created_at", "now() - interval '24 hours'")
        .execute()
    )
    rows = requests.data or []
    total = len(rows)
    total_cost = sum(float(r["cost_usd"]) for r in rows)
    latencies = sorted(r["latency_ms"] for r in rows)
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else None

    evals = (
        db.table("eval_scores")
        .select("quality_score")
        .eq("team_id", team_id)
        .gte("created_at", "now() - interval '24 hours'")
        .execute()
    )
    eval_rows = evals.data or []
    avg_quality = (
        round(sum(r["quality_score"] for r in eval_rows) / len(eval_rows), 1)
        if eval_rows else None
    )

    return ApiResponse(data={
        "requests_today": total,
        "avg_quality": avg_quality,
        "total_cost_usd": round(total_cost, 6),
        "p95_latency_ms": p95,
    })


@router.get("/distribution", response_model=ApiResponse)
async def distribution(auth: dict = Depends(verify_api_key_dep)) -> ApiResponse:
    db = get_db()
    rows = (
        db.table("requests")
        .select("complexity")
        .eq("team_id", auth["team_id"])
        .gte("created_at", "now() - interval '7 days'")
        .execute()
    ).data or []

    counts: dict[str, int] = {"simple": 0, "medium": 0, "complex": 0}
    for r in rows:
        counts[r["complexity"]] = counts.get(r["complexity"], 0) + 1

    total = sum(counts.values()) or 1
    return ApiResponse(data={
        "counts": counts,
        "percentages": {k: round(v / total * 100, 1) for k, v in counts.items()},
    })
