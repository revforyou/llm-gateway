"""
Pulls 5K samples from Bitext customer-support HuggingFace dataset
and inserts them into the tickets_seed Supabase table.

Usage:
    python backend/scripts/seed_dataset.py
"""
import os
import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from datasets import load_dataset
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
DATASET_NAME = "Bitext/Bitext-customer-support-llm-chatbot-training-dataset"
SAMPLE_SIZE = 5000
BATCH_SIZE = 200


def label_difficulty(text: str) -> str:
    text_lower = text.lower()
    escalation = {"legal", "fraud", "lawsuit", "refund", "manager", "supervisor"}
    if (
        len(text) > 800
        or any(k in text_lower for k in escalation)
        or text.count("\n\n") >= 2
    ):
        return "hard"
    faq = {"password", "reset", "login", "account", "billing", "cancel",
           "how do i", "how to", "what is", "where is"}
    if len(text) < 200 and any(k in text_lower for k in faq):
        return "easy"
    return "medium"


def main():
    print(f"Loading dataset: {DATASET_NAME}")
    ds = load_dataset(DATASET_NAME, split="train")
    print(f"Total rows: {len(ds)}")

    samples = ds.select(range(min(SAMPLE_SIZE, len(ds))))

    db = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    existing = db.table("tickets_seed").select("id", count="exact").execute()
    if existing.count and existing.count > 0:
        print(f"tickets_seed already has {existing.count} rows — skipping seed.")
        return

    rows = []
    for item in samples:
        text = item.get("instruction") or item.get("input") or item.get("text", "")
        if not text:
            continue
        rows.append({
            "source": "bitext-customer-support",
            "intent": item.get("intent"),
            "category": item.get("category"),
            "text": text[:2000],
            "difficulty": label_difficulty(text),
        })

    print(f"Inserting {len(rows)} rows in batches of {BATCH_SIZE}...")
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        db.table("tickets_seed").insert(batch).execute()
        print(f"  {min(i + BATCH_SIZE, len(rows))}/{len(rows)}")

    print("Done seeding tickets_seed.")


if __name__ == "__main__":
    main()
