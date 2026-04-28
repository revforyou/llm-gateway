"""Daily job: find responses without eval rows and re-enqueue them."""
import os
import httpx
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
QSTASH_TOKEN = os.environ["QSTASH_TOKEN"]
API_URL = os.environ["API_URL"]


def main():
    db = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    result = db.rpc(
        "find_unevaluated_responses",
        {"hours_back": 24}
    ).execute()

    if not result.data:
        # Fallback: manual join query
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
    else:
        unevaluated = [r["id"] for r in result.data]

    print(f"Found {len(unevaluated)} unevaluated responses")

    enqueued = 0
    for response_id in unevaluated:
        try:
            httpx.post(
                f"https://qstash.upstash.io/v2/publish/{API_URL}/v1/eval/run",
                headers={"Authorization": f"Bearer {QSTASH_TOKEN}"},
                json={"response_id": response_id},
                timeout=5.0,
            )
            enqueued += 1
        except Exception as e:
            print(f"Failed to enqueue {response_id}: {e}")

    print(f"Enqueued {enqueued} evals")


if __name__ == "__main__":
    main()
