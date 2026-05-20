from datetime import datetime, timedelta, timezone
from collections import defaultdict
from fastapi import APIRouter, Depends
from app.core.auth import verify_api_key_dep
from app.core.db import get_db
from app.models.schemas import ApiResponse

router = APIRouter(prefix="/v1/metrics", tags=["metrics"])

DEMO_TEAM = "00000000-0000-0000-0000-000000000001"


@router.get("/public", response_model=ApiResponse)
async def public_metrics() -> ApiResponse:
    """Public read-only metrics for the demo team — no auth required."""
    db = get_db()
    now = datetime.now(timezone.utc)
    day_ago = (now - timedelta(hours=24)).isoformat()
    week_ago = (now - timedelta(days=7)).isoformat()

    # Requests last 24h
    req_rows = (
        db.table("requests")
        .select("id, cost_usd, latency_ms, complexity, model_used, prompt, created_at")
        .eq("team_id", DEMO_TEAM)
        .gte("created_at", day_ago)
        .order("created_at", desc=True)
        .execute()
    ).data or []

    total = len(req_rows)
    total_cost = sum(float(r["cost_usd"]) for r in req_rows)
    latencies = sorted(r["latency_ms"] for r in req_rows)
    p95 = latencies[int(len(latencies) * 0.95)] if len(latencies) >= 5 else (latencies[-1] if latencies else None)

    # Complexity distribution last 7 days
    week_rows = (
        db.table("requests")
        .select("complexity")
        .eq("team_id", DEMO_TEAM)
        .gte("created_at", week_ago)
        .execute()
    ).data or []
    complexity_counts: dict[str, int] = {"simple": 0, "medium": 0, "complex": 0}
    for r in week_rows:
        c = r.get("complexity", "simple")
        complexity_counts[c] = complexity_counts.get(c, 0) + 1

    # Eval scores last 24h
    eval_rows = (
        db.table("eval_scores")
        .select("quality_score, hallucination_flag, refusal_flag, created_at")
        .eq("team_id", DEMO_TEAM)
        .gte("created_at", day_ago)
        .execute()
    ).data or []

    avg_quality = (
        round(sum(r["quality_score"] for r in eval_rows) / len(eval_rows), 1)
        if eval_rows else None
    )
    hallucination_rate = (
        round(sum(1 for r in eval_rows if r.get("hallucination_flag")) / len(eval_rows) * 100, 1)
        if eval_rows else None
    )

    # Quality trend grouped by hour
    hourly: dict = defaultdict(list)
    for row in eval_rows:
        try:
            dt = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
            hour_key = dt.replace(minute=0, second=0, microsecond=0).strftime("%H:00")
            hourly[hour_key].append(row["quality_score"])
        except Exception:
            continue

    quality_trend = [
        {"hour": h, "avg_quality": round(sum(scores) / len(scores), 1)}
        for h, scores in sorted(hourly.items())
    ]

    # Recent 10 requests
    recent = [
        {
            "complexity": r["complexity"],
            "model_used": r["model_used"],
            "latency_ms": r["latency_ms"],
            "cost_usd": float(r["cost_usd"]),
            "prompt_preview": (r.get("prompt") or "")[:80],
            "created_at": r["created_at"],
        }
        for r in req_rows[:10]
    ]

    return ApiResponse(data={
        "stats": {
            "requests_today": total,
            "avg_quality": avg_quality,
            "total_cost_usd": round(total_cost, 6),
            "p95_latency_ms": p95,
            "hallucination_rate": hallucination_rate,
        },
        "complexity_distribution": complexity_counts,
        "quality_trend": quality_trend,
        "recent_requests": recent,
    })


@router.get("/overview", response_model=ApiResponse)
async def overview(auth: dict = Depends(verify_api_key_dep)) -> ApiResponse:
    db = get_db()
    team_id = auth["team_id"]
    now = datetime.now(timezone.utc)
    day_ago = (now - timedelta(hours=24)).isoformat()

    requests = (
        db.table("requests")
        .select("id, cost_usd, latency_ms, gateway_overhead_ms")
        .eq("team_id", team_id)
        .gte("created_at", day_ago)
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
        .gte("created_at", day_ago)
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
    now = datetime.now(timezone.utc)
    week_ago = (now - timedelta(days=7)).isoformat()

    rows = (
        db.table("requests")
        .select("complexity")
        .eq("team_id", auth["team_id"])
        .gte("created_at", week_ago)
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
