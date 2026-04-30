"""
Trains the complexity classifier on the Bitext dataset.
Produces backend/app/gateway/classifier.pkl.

Target distribution: 70% simple / 25% medium / 5% complex (±5pp).

Usage:
    python backend/scripts/train_classifier.py
    python backend/scripts/train_classifier.py --from-supabase
"""
import os
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

OUTPUT_PATH = Path(__file__).parent.parent / "app" / "gateway" / "classifier.pkl"

# Bitext dataset has short texts (10-150 chars), so rules are keyword-based.

COMPLEX_KEYWORDS = {
    "complaint", "complain", "speak to", "speak with", "human agent",
    "customer service", "manager", "supervisor", "charged twice", "charged wrong",
    "wrongly charged", "dispute", "fraud", "unauthorized", "legal",
    "refund", "get my money", "money back", "chargeback", "escalate",
    "not acceptable", "unacceptable", "demand",
}

# Simple = informational / single-action requests
SIMPLE_KEYWORDS = {
    "how do i", "how to", "how can i", "what is", "where is", "where can i",
    "when will", "can i", "is it possible", "do you accept",
    "track my order", "track order", "order status", "where is my order",
    "reset my password", "forgot my password", "recover password",
    "newsletter", "subscribe", "unsubscribe",
    "check", "view", "see my", "find my", "show me",
    "payment methods", "accepted payments",
}


def label(text: str, intent: str = "", category: str = "") -> str:
    text_lower = text.lower()
    intent_lower = (intent or "").lower()

    # Complex: high-stakes, escalation, financial dispute
    complex_intents = {
        "contact_human_agent", "complaint", "payment_issue",
        "get_refund", "track_refund",
    }
    if intent_lower in complex_intents:
        return "complex"
    if any(k in text_lower for k in COMPLEX_KEYWORDS):
        return "complex"

    # Simple: informational, single-action, standard FAQ
    simple_intents = {
        "track_order", "recover_password", "check_payment_methods",
        "check_refund_policy", "delivery_period", "newsletter_subscription",
        "check_invoice", "check_cancellation_fee",
    }
    if intent_lower in simple_intents:
        return "simple"
    if any(k in text_lower for k in SIMPLE_KEYWORDS):
        return "simple"

    return "medium"


def check_distribution(labels: list[str]) -> dict:
    from collections import Counter
    counts = Counter(labels)
    total = len(labels)
    return {k: round(counts.get(k, 0) / total * 100, 1) for k in ["simple", "medium", "complex"]}


def load_from_huggingface(n: int = 5000) -> list[dict]:
    from datasets import load_dataset
    print("Downloading from HuggingFace...")
    ds = load_dataset(
        "Bitext/Bitext-customer-support-llm-chatbot-training-dataset",
        split="train",
    )
    items = []
    for item in ds.select(range(min(n, len(ds)))):
        text = item.get("instruction") or item.get("input") or item.get("text", "")
        if text:
            items.append({
                "text": text[:2000],
                "intent": item.get("intent", ""),
                "category": item.get("category", ""),
            })
    return items


def load_from_supabase() -> list[dict]:
    from supabase import create_client
    db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    result = db.table("tickets_seed").select("text, intent, difficulty").execute()
    return [{"text": r["text"], "intent": r.get("intent", ""), "category": ""}
            for r in result.data if r.get("text")]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-supabase", action="store_true")
    args = parser.parse_args()

    items = load_from_supabase() if args.from_supabase else load_from_huggingface()
    print(f"Loaded {len(items)} samples")

    texts = [i["text"] for i in items]
    labels = [label(i["text"], i.get("intent", ""), i.get("category", "")) for i in items]

    dist = check_distribution(labels)
    print(f"Label distribution: {dist}")

    targets = {"simple": 70, "medium": 25, "complex": 5}
    for cls, target in targets.items():
        actual = dist.get(cls, 0)
        if abs(actual - target) > 5:
            print(f"NOTE: {cls}={actual}% vs target {target}% (±5pp). "
                  f"Continuing — model learns patterns from text.")

    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )

    pipe = Pipeline([
        ("tfidf", TfidfVectorizer(max_features=5000, ngram_range=(1, 2), sublinear_tf=True)),
        ("clf", LogisticRegression(class_weight="balanced", max_iter=1000, C=1.0)),
    ])
    pipe.fit(X_train, y_train)

    y_pred = pipe.predict(X_test)
    print("\nClassification report (test set):")
    print(classification_report(y_test, y_pred))

    holdout_dist = check_distribution(list(y_pred))
    print(f"Holdout prediction distribution: {holdout_dist}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, OUTPUT_PATH)
    print(f"\nSaved to {OUTPUT_PATH}")

    # Quick sanity checks
    sanity = [
        ("How do I reset my password?", "simple"),
        ("I need to speak to a human agent immediately.", "complex"),
        ("Where is my order?", "simple"),
        ("I was charged twice and want my money back.", "complex"),
        ("How do I cancel my subscription?", "medium"),
    ]
    print("\nSanity checks:")
    for text, expected in sanity:
        pred = pipe.predict([text])[0]
        status = "✓" if pred == expected else f"✗ (got {pred})"
        print(f"  [{status}] '{text[:50]}' → {pred}")


if __name__ == "__main__":
    main()
