"""Called by keep-warm GitHub Action. Touches DB, Redis, and backend."""
import os
import sys
import httpx

API_URL = os.environ.get("API_URL", "http://localhost:8000")
INTERNAL_CRON_SECRET = os.environ.get("INTERNAL_CRON_SECRET", "")


def main():
    errors = []
    try:
        r = httpx.get(f"{API_URL}/health", timeout=10.0)
        r.raise_for_status()
        print(f"Health: {r.json()}")
    except Exception as e:
        errors.append(f"health: {e}")

    try:
        r = httpx.post(
            f"{API_URL}/v1/internal/keep-warm",
            headers={"X-Cron-Secret": INTERNAL_CRON_SECRET},
            timeout=10.0,
        )
        r.raise_for_status()
        print(f"Keep-warm: {r.json()}")
    except Exception as e:
        errors.append(f"keep-warm: {e}")

    if errors:
        print(f"Errors: {errors}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
