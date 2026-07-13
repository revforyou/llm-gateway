"""Drift detection: compares last-1-hour metrics against 7-day rolling baseline."""
from datetime import datetime, timedelta, timezone

import httpx
from app.core.db import get_db
from app.core.config import settings


async def run_drift_check() -> None:
    db = get_db()

    teams = db.table("teams").select("id").execute().data or []
    for team in teams:
        team_id = team["id"]
        await _check_team(db, team_id)


async def _check_team(db, team_id: str) -> None:
    # PostgREST filter values are literals, not SQL — "now() - interval ..." is
    # rejected as an invalid timestamp. Compute the window bounds in Python.
    now = datetime.now(timezone.utc)
    seven_days_ago = (now - timedelta(days=7)).isoformat()
    one_hour_ago = (now - timedelta(hours=1)).isoformat()

    # 7-day baseline quality
    baseline_rows = (
        db.table("eval_scores")
        .select("quality_score")
        .eq("team_id", team_id)
        .gte("created_at", seven_days_ago)
        .lte("created_at", one_hour_ago)
        .execute()
    ).data or []

    if len(baseline_rows) < 20:
        return

    baseline_quality = sum(r["quality_score"] for r in baseline_rows) / len(baseline_rows)

    # Last-1-hour quality
    recent_rows = (
        db.table("eval_scores")
        .select("quality_score")
        .eq("team_id", team_id)
        .gte("created_at", one_hour_ago)
        .execute()
    ).data or []

    if len(recent_rows) < 5:
        return

    recent_quality = sum(r["quality_score"] for r in recent_rows) / len(recent_rows)

    delta_pct = (recent_quality - baseline_quality) / max(baseline_quality, 1) * 100

    if delta_pct < -10:
        severity = "critical" if delta_pct < -25 else "warning"
        db.table("drift_events").insert({
            "team_id": team_id,
            "metric_name": "quality_score",
            "baseline_value": round(baseline_quality, 2),
            "current_value": round(recent_quality, 2),
            "delta_pct": round(delta_pct, 2),
            "severity": severity,
        }).execute()

        if settings.alert_webhook_url:
            await _send_alert(team_id, "quality_score", baseline_quality,
                              recent_quality, delta_pct, severity)


async def _send_alert(team_id, metric, baseline, current, delta_pct, severity):
    import json, hashlib, hmac, time
    payload = json.dumps({
        "team_id": team_id, "metric": metric,
        "baseline": baseline, "current": current,
        "delta_pct": delta_pct, "severity": severity,
    })
    sig = hmac.new(
        settings.alert_webhook_secret.encode(),
        payload.encode(),
        "sha256"
    ).hexdigest()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                settings.alert_webhook_url,
                content=payload,
                headers={"Content-Type": "application/json",
                         "X-Signature": f"sha256={sig}"},
            )
    except Exception:
        pass
