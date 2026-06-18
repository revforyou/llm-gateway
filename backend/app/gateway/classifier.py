"""
Hybrid complexity classifier:
- Rule-based for "complex" detection (escalation keywords, length)
- Trained ML model (TF-IDF + LogReg) for simple vs medium
- Falls back to rule-based if model not loaded
"""
import hashlib
import json
import os
import joblib
from app.core.cache import get_redis

_model = None
MODEL_PATH = os.path.join(os.path.dirname(__file__), "classifier.pkl")

COMPLEX_KEYWORDS = {
    "speak to", "speak with", "human agent", "customer service rep",
    "manager", "supervisor", "charged twice", "charged wrong",
    "wrongly charged", "dispute", "fraud", "unauthorized charge",
    "legal action", "get my money back", "money back", "chargeback",
    "not acceptable", "unacceptable", "demand a refund", "escalate",
    "file a complaint",
}


_model_load_failed = False


def _load_model():
    """Load the pickled model once. If it fails (e.g. sklearn version skew
    between training and runtime), mark it failed and never retry — the caller
    falls back to rule-based classification instead of crashing the gateway."""
    global _model, _model_load_failed
    if _model is None and not _model_load_failed and os.path.exists(MODEL_PATH):
        try:
            _model = joblib.load(MODEL_PATH)
        except Exception as e:
            _model_load_failed = True
            print(f"[classifier] model load failed, using rule-based fallback: {e}")
    return _model


def _is_complex(text: str) -> bool:
    text_lower = text.lower()
    if len(text) > 800:
        return True
    if text.count("\n\n") >= 2:
        return True
    return any(k in text_lower for k in COMPLEX_KEYWORDS)


def classify(text: str) -> tuple[str, float]:
    prompt_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
    cache_key = f"clf:{prompt_hash}"

    redis = get_redis()
    cached = redis.get(cache_key)
    if cached:
        result = json.loads(cached)
        return result["complexity"], result["score"]

    # Complex detection always takes priority (rule-based, reliable)
    if _is_complex(text):
        complexity, score = "complex", 0.90
    else:
        model = _load_model()
        if model is not None:
            try:
                proba = model.predict_proba([text])[0]
                classes = list(model.classes_)
                idx = int(proba.argmax())
                complexity = classes[idx]
                score = float(proba[idx])
            except Exception as e:
                # Predict-time failure (version skew, bad input) — never 500.
                print(f"[classifier] predict failed, using rule-based fallback: {e}")
                complexity, score = _rule_based_classify(text)
        else:
            complexity, score = _rule_based_classify(text)

    redis.setex(cache_key, 3600, json.dumps({"complexity": complexity, "score": score}))
    return complexity, score


def _rule_based_classify(text: str) -> tuple[str, float]:
    text_lower = text.lower()
    # Specific simple patterns — informational or single-action standard requests
    simple_patterns = {
        "reset my password", "forgot my password", "recover my password",
        "track my order", "where is my order", "order status",
        "track my refund", "where is my refund",
        "payment methods", "accepted payment", "payment options",
        "delivery time", "shipping time", "how long does",
        "newsletter", "unsubscribe", "subscribe",
        "opening hours", "contact details", "phone number",
    }
    if len(text) < 300 and any(k in text_lower for k in simple_patterns):
        return "simple", 0.88
    return "medium", 0.75
