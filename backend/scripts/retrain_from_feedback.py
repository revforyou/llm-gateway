"""
Weekly retraining from eval feedback.

Logic:
  - Pull requests from the last 7 days that have eval scores.
  - If a 'simple'-routed request scored quality < 65, it was likely misrouted
    → relabel as 'medium' and add to training data.
  - If a 'complex'-routed request scored quality > 85, it was likely over-served
    → relabel as 'medium' and add to training data.
  - Only retrain when >= MIN_CORRECTIONS feedback corrections are available
    (avoids overfitting on noise).
  - Combines feedback examples with original Bitext data and retrains from scratch.

Usage (called by GitHub Actions weekly):
    python backend/scripts/retrain_from_feedback.py
"""
import os
import sys
import json
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
from supabase import create_client

MIN_CORRECTIONS = 10          # don't retrain on fewer corrections than this
QUALITY_LOW_THRESHOLD = 65    # simple-routed + score < 65 → misrouted, relabel medium
QUALITY_HIGH_THRESHOLD = 85   # complex-routed + score > 85 → over-served, relabel medium

OUTPUT_PATH = Path(__file__).parent.parent / "app" / "gateway" / "classifier.pkl"
METRICS_PATH = Path(__file__).parent.parent / "app" / "gateway" / "classifier_metrics.json"

COMPLEX_KEYWORDS = {
    "complaint", "complain", "speak to", "speak with", "human agent",
    "customer service", "manager", "supervisor", "charged twice", "charged wrong",
    "wrongly charged", "dispute", "fraud", "unauthorized", "legal",
    "refund", "get my money", "money back", "chargeback", "escalate",
    "not acceptable", "unacceptable", "demand",
}
SIMPLE_KEYWORDS = {
    "how do i", "how to", "how can i", "what is", "where is", "where can i",
    "when will", "can i", "is it possible", "do you accept",
    "track my order", "track order", "order status", "where is my order",
    "reset my password", "forgot my password", "recover password",
    "newsletter", "subscribe", "unsubscribe",
    "check", "view", "see my", "find my", "show me",
    "payment methods", "accepted payments",
}


def label_text(text: str, intent: str = "") -> str:
    text_lower = text.lower()
    intent_lower = (intent or "").lower()
    complex_intents = {"contact_human_agent", "complaint", "payment_issue", "get_refund", "track_refund"}
    if intent_lower in complex_intents or any(k in text_lower for k in COMPLEX_KEYWORDS):
        return "complex"
    simple_intents = {
        "track_order", "recover_password", "check_payment_methods",
        "check_refund_policy", "delivery_period", "newsletter_subscription",
        "check_invoice", "check_cancellation_fee",
    }
    if intent_lower in simple_intents or any(k in text_lower for k in SIMPLE_KEYWORDS):
        return "simple"
    return "medium"


def load_bitext(n: int = 5000) -> tuple[list[str], list[str]]:
    from datasets import load_dataset
    print("Loading Bitext from HuggingFace...")
    ds = load_dataset(
        "Bitext/Bitext-customer-support-llm-chatbot-training-dataset",
        split="train",
    )
    texts, labels = [], []
    for item in ds.select(range(min(n, len(ds)))):
        text = item.get("instruction") or item.get("input") or item.get("text", "")
        if text:
            texts.append(text[:2000])
            labels.append(label_text(text, item.get("intent", "")))
    return texts, labels


def load_feedback_corrections(db) -> tuple[list[str], list[str]]:
    """
    Returns (texts, corrected_labels) for requests where routing was wrong.
    """
    # Join requests + eval_scores for last 7 days
    # Only look at high-confidence eval scores so we trust the quality signal
    rows = (
        db.table("eval_scores")
        .select("response_id, quality_score, judge_confidence, flags")
        .eq("judge_confidence", "high")
        .gte("created_at", "now() - interval '7 days'")
        .execute()
    ).data or []

    response_ids = [r["response_id"] for r in rows]
    if not response_ids:
        return [], []

    quality_map = {r["response_id"]: r["quality_score"] for r in rows}

    # Get corresponding requests via responses table
    resp_rows = (
        db.table("responses")
        .select("id, request_id")
        .in_("id", response_ids)
        .execute()
    ).data or []

    request_id_map = {r["id"]: r["request_id"] for r in resp_rows}
    request_ids = list(request_id_map.values())
    if not request_ids:
        return [], []

    req_rows = (
        db.table("requests")
        .select("id, prompt, complexity")
        .in_("id", request_ids)
        .execute()
    ).data or []

    req_map = {r["id"]: r for r in req_rows}

    corrections_texts, corrections_labels = [], []
    for resp_id, req_id in request_id_map.items():
        req = req_map.get(req_id)
        if not req:
            continue
        score = quality_map.get(resp_id)
        if score is None:
            continue

        complexity = req["complexity"]
        prompt = req["prompt"]

        if complexity == "simple" and score < QUALITY_LOW_THRESHOLD:
            # Routed too cheap → should have been medium
            corrections_texts.append(prompt)
            corrections_labels.append("medium")

        elif complexity == "complex" and score > QUALITY_HIGH_THRESHOLD:
            # Routed too expensive → medium would have sufficed
            corrections_texts.append(prompt)
            corrections_labels.append("medium")

    return corrections_texts, corrections_labels


def retrain(base_texts, base_labels, correction_texts, correction_labels):
    # Weight feedback corrections 3× to ensure they influence the decision boundary
    all_texts = base_texts + correction_texts * 3
    all_labels = base_labels + correction_labels * 3

    X_train, X_test, y_train, y_test = train_test_split(
        all_texts, all_labels, test_size=0.2, random_state=42, stratify=all_labels
    )

    pipe = Pipeline([
        ("tfidf", TfidfVectorizer(max_features=5000, ngram_range=(1, 2), sublinear_tf=True)),
        ("clf", LogisticRegression(class_weight="balanced", max_iter=1000, C=1.0)),
    ])
    pipe.fit(X_train, y_train)

    y_pred = pipe.predict(X_test)
    print("\nClassification report (post-retrain test set):")
    print(classification_report(y_test, y_pred))

    report = classification_report(y_test, y_pred, output_dict=True)
    metrics = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "feedback_corrections": len(correction_texts),
        "model": "tfidf+logreg",
        "note": "Retrained from eval feedback. Complex tier is rule-based.",
        "accuracy": round(accuracy_score(y_test, y_pred), 4),
        "per_class": {
            cls: {
                "precision": round(report[cls]["precision"], 4),
                "recall": round(report[cls]["recall"], 4),
                "f1": round(report[cls]["f1-score"], 4),
                "support": int(report[cls]["support"]),
            }
            for cls in ["simple", "medium", "complex"]
            if cls in report
        },
    }

    return pipe, metrics


def main():
    supabase_url = os.environ["SUPABASE_URL"]
    supabase_key = os.environ["SUPABASE_SERVICE_KEY"]
    db = create_client(supabase_url, supabase_key)

    print("Loading feedback corrections from eval data...")
    correction_texts, correction_labels = load_feedback_corrections(db)
    print(f"Found {len(correction_texts)} corrections")

    if len(correction_texts) < MIN_CORRECTIONS:
        print(f"Only {len(correction_texts)} corrections (need {MIN_CORRECTIONS}). Skipping retrain.")
        return

    from collections import Counter
    print(f"Correction label distribution: {dict(Counter(correction_labels))}")

    base_texts, base_labels = load_bitext(n=5000)
    print(f"Loaded {len(base_texts)} Bitext base samples")

    pipe, metrics = retrain(base_texts, base_labels, correction_texts, correction_labels)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, OUTPUT_PATH)
    print(f"\nSaved updated classifier to {OUTPUT_PATH}")

    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Saved metrics to {METRICS_PATH}")


if __name__ == "__main__":
    main()
