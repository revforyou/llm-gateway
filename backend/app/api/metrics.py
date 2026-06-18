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
        .select("id, cost_usd, latency_ms, gateway_overhead_ms, complexity, model_used, prompt, created_at")
        .eq("team_id", DEMO_TEAM)
        .gte("created_at", day_ago)
        .order("created_at", desc=True)
        .execute()
    ).data or []

    total = len(req_rows)
    total_cost = sum(float(r["cost_usd"]) for r in req_rows)
    latencies = sorted(r["latency_ms"] for r in req_rows)
    p95 = latencies[int(len(latencies) * 0.95)] if len(latencies) >= 5 else (latencies[-1] if latencies else None)

    # Gateway overhead = our own processing time (auth, classify, route, DB writes),
    # excluding LLM inference. Median is the honest figure — p95/max are inflated by
    # provider retry/backoff waits that get attributed to overhead.
    overheads = sorted(
        r["gateway_overhead_ms"] for r in req_rows
        if r.get("gateway_overhead_ms") is not None and r["gateway_overhead_ms"] >= 0
    )
    gateway_overhead_ms = overheads[len(overheads) // 2] if overheads else None

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

    # Eval scores last 24h — exclude low-confidence (parse-failed) scores
    eval_rows = (
        db.table("eval_scores")
        .select("quality_score, hallucination_flag, refusal_flag, judge_confidence, created_at")
        .eq("team_id", DEMO_TEAM)
        .gte("created_at", day_ago)
        .execute()
    ).data or []

    high_conf = [r for r in eval_rows if r.get("judge_confidence") != "low"]
    scored_rows = high_conf if high_conf else eval_rows  # fall back if all low-conf

    avg_quality = (
        round(sum(r["quality_score"] for r in scored_rows) / len(scored_rows), 1)
        if scored_rows else None
    )
    hallucination_rate = (
        round(sum(1 for r in scored_rows if r.get("hallucination_flag")) / len(scored_rows) * 100, 1)
        if scored_rows else None
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

    # Per-model stats from today's requests
    model_buckets: dict = {}
    for r in req_rows:
        m = r["model_used"]
        if m not in model_buckets:
            model_buckets[m] = {"count": 0, "total_latency": 0, "total_cost": 0.0}
        model_buckets[m]["count"] += 1
        model_buckets[m]["total_latency"] += r["latency_ms"]
        model_buckets[m]["total_cost"] += float(r["cost_usd"])

    model_stats = {
        m: {
            "count": v["count"],
            "avg_latency_ms": round(v["total_latency"] / v["count"]) if v["count"] else 0,
            "total_cost_usd": round(v["total_cost"], 6),
        }
        for m, v in model_buckets.items()
    }

    # Estimate savings vs always routing to 70B
    big_model = "llama-3.3-70b-versatile"
    big_avg_cost = (
        model_buckets[big_model]["total_cost"] / model_buckets[big_model]["count"]
        if big_model in model_buckets and model_buckets[big_model]["count"] > 0
        else 0.0003
    )
    hypothetical_cost = big_avg_cost * total
    cost_savings_usd = round(max(0.0, hypothetical_cost - total_cost), 6)
    savings_pct = round((cost_savings_usd / hypothetical_cost * 100) if hypothetical_cost > 0 else 0, 1)

    # Route efficiency — use same 7-day window as complexity_counts
    week_total = sum(complexity_counts.values()) or 1
    cheap_count = complexity_counts.get("simple", 0)
    cheap_pct = round(cheap_count / week_total * 100, 1)

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
            "gateway_overhead_ms": gateway_overhead_ms,
            "hallucination_rate": hallucination_rate,
            "cost_savings_usd": cost_savings_usd,
            "savings_pct": savings_pct,
            "cheap_route_pct": cheap_pct,
        },
        "complexity_distribution": complexity_counts,
        "model_stats": model_stats,
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
