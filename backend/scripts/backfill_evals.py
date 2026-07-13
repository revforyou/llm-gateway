"""Daily job: find responses without eval rows and evaluate them.

Safety net for the in-process eval path (app/api/chat.py): if the gateway restarts
mid-eval, that eval is lost, and this job catches it the next day. It POSTs each
missed response straight to the gateway's /v1/eval/run endpoint (which runs the
eval synchronously) — no external queue involved.

Capped per run and lightly throttled to stay within the Gemini free-tier rate
limit (~15 req/min). With in-process evals handling live traffic, the backlog is
normally tiny, so the cap just protects the Action window on the rare large day.
"""
import os
import time

import httpx
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
API_URL = os.environ["API_URL"].rstrip("/")
BACKFILL_LIMIT = int(os.environ.get("BACKFILL_LIMIT", "30"))
THROTTLE_SECONDS = float(os.environ.get("BACKFILL_THROTTLE_SECONDS", "4"))


def main():
    db = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    try:
        result = db.rpc(
            "find_unevaluated_responses",
            {"hours_back": 24}
        ).execute()
        unevaluated = [r["id"] for r in (result.data or [])]
    except Exception as e:
        print(f"RPC not available ({e}), falling back to manual query")
        unevaluated = []

    if not unevaluated:
        responses = (
            db.table("responses")
            .select("id")
            .gte("created_at", "now() - interval '24 hours'")
            .execute()
        ).data or []

        eval_ids = set(
            r["response_id"]
            for r in (
                db.table("eval_scores")
                .select("response_id")
                .gte("created_at", "now() - interval '25 hours'")
                .execute()
            ).data or []
        )

        unevaluated = [r["id"] for r in responses if r["id"] not in eval_ids]

    print(f"Found {len(unevaluated)} unevaluated responses")

    batch = unevaluated[:BACKFILL_LIMIT]
    if len(unevaluated) > BACKFILL_LIMIT:
        print(f"Capping to {BACKFILL_LIMIT} this run; remainder catches up next run")

    evaluated = 0
    for i, response_id in enumerate(batch):
        try:
            r = httpx.post(
                f"{API_URL}/v1/eval/run",
                json={"response_id": response_id},
                timeout=40.0,
            )
            r.raise_for_status()
            evaluated += 1
        except Exception as e:
            print(f"Failed to evaluate {response_id}: {e}")
        if i < len(batch) - 1:
            time.sleep(THROTTLE_SECONDS)

    print(f"Evaluated {evaluated}/{len(batch)} responses")


if __name__ == "__main__":
    main()
