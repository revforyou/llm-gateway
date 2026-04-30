"""
Idempotently creates the demo team's API key and showcase experiment.
Run once after deploy.

Usage:
    python backend/scripts/bootstrap_demo.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from supabase import create_client
from app.core.security import generate_api_key

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
DEMO_TEAM_ID = os.environ.get("DEMO_TEAM_ID", "00000000-0000-0000-0000-000000000001")


def main():
    db = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    # Ensure demo team exists
    db.table("teams").upsert({
        "id": DEMO_TEAM_ID,
        "name": "Demo Team",
        "plan": "free",
    }, on_conflict="id").execute()
    print(f"Demo team: {DEMO_TEAM_ID}")

    # Create demo API key if none exists
    existing_keys = (
        db.table("api_keys")
        .select("id, key_prefix")
        .eq("team_id", DEMO_TEAM_ID)
        .is_("revoked_at", "null")
        .execute()
    ).data

    if existing_keys:
        print(f"Demo API key already exists: {existing_keys[0]['key_prefix']}...")
        print("Set DEMO_API_KEY in GitHub secrets to this key's plaintext.")
    else:
        plaintext, prefix, hashed = generate_api_key()
        db.table("api_keys").insert({
            "team_id": DEMO_TEAM_ID,
            "name": "Demo Traffic Key",
            "key_hash": hashed,
            "key_prefix": prefix,
        }).execute()
        print(f"\nCreated demo API key:")
        print(f"  Prefix:    {prefix}")
        print(f"  Plaintext: {plaintext}")
        print(f"\n  *** Save this as DEMO_API_KEY in GitHub secrets — shown once! ***\n")

    # Create showcase experiment if not present
    existing_exp = (
        db.table("experiments")
        .select("id, name")
        .eq("team_id", DEMO_TEAM_ID)
        .eq("name", "Tuned-Support-Prompt vs Vanilla-Prompt")
        .execute()
    ).data

    if existing_exp:
        print(f"Showcase experiment already exists: {existing_exp[0]['id']}")
    else:
        result = db.table("experiments").insert({
            "team_id": DEMO_TEAM_ID,
            "name": "Tuned-Support-Prompt vs Vanilla-Prompt",
            "hypothesis": "A tuned support prompt produces higher quality scores than a vanilla prompt on the same model.",
            "variant_a": {
                "provider": "groq",
                "model": "llama-3.1-8b-instant",
                "prompt_version": "v1_vanilla",
            },
            "variant_b": {
                "provider": "groq",
                "model": "llama-3.1-8b-instant",
                "prompt_version": "v2_tuned_support",
            },
            "traffic_split": 0.5,
            "min_sample_size": 100,
            "max_sample_size": 2000,
            "status": "running",
        }).execute()
        print(f"Created showcase experiment: {result.data[0]['id']}")

    print("\nBootstrap complete.")


if __name__ == "__main__":
    main()
