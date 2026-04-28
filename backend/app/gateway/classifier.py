import hashlib
import json
import os
import joblib
from app.core.cache import get_redis

_model = None
MODEL_PATH = os.path.join(os.path.dirname(__file__), "classifier.pkl")


def _load_model():
    global _model
    if _model is None and os.path.exists(MODEL_PATH):
        _model = joblib.load(MODEL_PATH)
    return _model


def classify(text: str) -> tuple[str, float]:
    prompt_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
    cache_key = f"clf:{prompt_hash}"

    redis = get_redis()
    cached = redis.get(cache_key)
    if cached:
        result = json.loads(cached)
        return result["complexity"], result["score"]

    model = _load_model()
    if model is None:
        complexity, score = _rule_based_classify(text)
    else:
        proba = model.predict_proba([text])[0]
        classes = model.classes_
        idx = proba.argmax()
        complexity = classes[idx]
        score = float(proba[idx])

    redis.setex(cache_key, 3600, json.dumps({"complexity": complexity, "score": score}))
    return complexity, score


def _rule_based_classify(text: str) -> tuple[str, float]:
    text_lower = text.lower()
    escalation_keywords = {"legal", "fraud", "lawsuit", "refund", "manager", "supervisor"}

    if (
        len(text) > 800
        or any(k in text_lower for k in escalation_keywords)
        or text.count("\n\n") >= 2
    ):
        return "complex", 0.85

    faq_keywords = {
        "password", "reset", "login", "account", "billing", "cancel",
        "how do i", "how to", "what is", "where is",
    }
    if len(text) < 200 and any(k in text_lower for k in faq_keywords):
        return "simple", 0.90

    return "medium", 0.75
