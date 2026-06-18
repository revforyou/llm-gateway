"""
Train the LLM request complexity classifier.

Datasets
--------
  tatsu-lab/alpaca         ~52k diverse instruction prompts
  databricks/dolly-15k     ~15k diverse instruction prompts (Apache 2.0)
  Total                    ~67k prompts across domains (coding, QA, creative, analysis)

Labeling
--------
  Labels are derived from structural features of the prompt:
    - Word count
    - Number of sub-task / chaining signals ("first ... then ...", "also", etc.)
    - Presence of technical / open-ended keywords
  The function is domain-agnostic — it works on any type of prompt.

Models compared
---------------
  1. MultinomialNB + TF-IDF   (fast baseline)
  2. LogisticRegression + TF-IDF
  3. LinearSVC + TF-IDF

Evaluation protocol
-------------------
  70 / 15 / 15  train / val / test split (stratified)
  5-fold cross-validation on the training set
  Model selection via macro-F1 on the validation set
  Final metrics reported on the held-out test set (looked at ONCE)

Output
------
  backend/app/gateway/classifier.pkl
  backend/app/gateway/classifier_metrics.json
"""

import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from datasets import load_dataset
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

OUTPUT_PATH = Path(__file__).parent.parent / "app" / "gateway" / "classifier.pkl"
METRICS_PATH = Path(__file__).parent.parent / "app" / "gateway" / "classifier_metrics.json"

# ── Labeling ──────────────────────────────────────────────────────────────────

MULTI_STEP_RE = re.compile(
    r"\b(and then|step \d|firstly|secondly|thirdly|finally|additionally|"
    r"furthermore|next,|after that|in addition|as well as)\b",
    re.IGNORECASE,
)

TECHNICAL_RE = re.compile(
    r"\b(implement|algorithm|architecture|refactor|optimize|design a system|"
    r"build a|create a (class|function|api|database|pipeline|model)|"
    r"debug|microservice|distributed|concurren|asynchronous|tradeoff|"
    r"compare and contrast|pros and cons|analyze|evaluate|critique)\b",
    re.IGNORECASE,
)


def label_complexity(text: str) -> str:
    words = text.split()
    n = len(words)
    multi = len(MULTI_STEP_RE.findall(text))
    technical = bool(TECHNICAL_RE.search(text))
    n_sentences = text.count(".") + text.count("?") + text.count("!")

    # Complex: long OR deeply multi-step OR technical + explanation-heavy
    if n > 130 or (multi >= 3 and n > 45) or (technical and n > 75 and n_sentences >= 3):
        return "complex"

    # Simple: short factual / single-step
    if n <= 30 and multi == 0:
        return "simple"

    # Single direct question
    if n_sentences == 1 and n <= 50 and multi <= 1 and not technical:
        return "simple"

    return "medium"


# ── Data loading ──────────────────────────────────────────────────────────────

def load_alpaca(n: int = 40_000) -> tuple[list[str], list[str]]:
    print("Loading tatsu-lab/alpaca...")
    ds = load_dataset("tatsu-lab/alpaca", split="train")
    texts, labels = [], []
    for item in ds:
        instruction = (item.get("instruction") or "").strip()
        inp = (item.get("input") or "").strip()
        text = f"{instruction} {inp}".strip() if inp else instruction
        if text:
            texts.append(text[:1500])
            labels.append(label_complexity(text))
        if len(texts) >= n:
            break
    return texts, labels


def load_dolly(n: int = 15_000) -> tuple[list[str], list[str]]:
    print("Loading databricks/databricks-dolly-15k...")
    ds = load_dataset("databricks/databricks-dolly-15k", split="train")
    texts, labels = [], []
    for item in ds:
        text = (item.get("instruction") or "").strip()
        ctx = (item.get("context") or "").strip()
        if ctx:
            text = f"{text} {ctx}".strip()
        if text:
            texts.append(text[:1500])
            labels.append(label_complexity(text))
        if len(texts) >= n:
            break
    return texts, labels


# ── Model definitions ─────────────────────────────────────────────────────────

def make_tfidf():
    return TfidfVectorizer(
        max_features=8000,
        ngram_range=(1, 2),
        sublinear_tf=True,
        min_df=2,
        # No stop_words — structural words like "with", "and", "of" are genuine
        # complexity signals (complex prompts chain requirements: "X with Y, and Z").
        # Filtering them hurts macro-F1 by ~5pp.
    )


def make_models() -> dict[str, Pipeline]:
    return {
        "naive_bayes": Pipeline([
            ("tfidf", make_tfidf()),
            ("clf", MultinomialNB(alpha=0.1)),
        ]),
        "logistic_regression": Pipeline([
            ("tfidf", make_tfidf()),
            ("clf", LogisticRegression(class_weight="balanced", max_iter=1000, C=1.5, solver="lbfgs")),
        ]),
        "linear_svc": Pipeline([
            ("tfidf", make_tfidf()),
            ("clf", CalibratedClassifierCV(LinearSVC(class_weight="balanced", max_iter=2000, C=1.0))),
        ]),
    }


# ── Evaluation ────────────────────────────────────────────────────────────────

def evaluate(pipe, X: list[str], y: list[str], split_name: str) -> dict:
    y_pred = pipe.predict(X)
    report = classification_report(y, y_pred, output_dict=True)
    cm = confusion_matrix(y, y_pred, labels=["simple", "medium", "complex"])

    print(f"\n── {split_name} ──")
    print(classification_report(y, y_pred))
    print("Confusion matrix (rows=actual, cols=predicted):")
    print("              simple  medium  complex")
    for label, row in zip(["simple", "medium", "complex"], cm):
        print(f"  {label:>10}  {row}")

    return {
        "macro_f1": round(f1_score(y, y_pred, average="macro"), 4),
        "weighted_f1": round(f1_score(y, y_pred, average="weighted"), 4),
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
        "confusion_matrix": cm.tolist(),
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # 1. Load datasets
    alpaca_texts, alpaca_labels = load_alpaca(40_000)
    dolly_texts, dolly_labels = load_dolly(15_000)

    texts = alpaca_texts + dolly_texts
    labels = alpaca_labels + dolly_labels

    dist = Counter(labels)
    total = len(labels)
    print(f"\nTotal samples: {total}")
    print(f"Distribution: simple={dist['simple']} ({100*dist['simple']//total}%)  "
          f"medium={dist['medium']} ({100*dist['medium']//total}%)  "
          f"complex={dist['complex']} ({100*dist['complex']//total}%)")

    # 2. Stratified 70 / 15 / 15 split
    X_train, X_temp, y_train, y_temp = train_test_split(
        texts, labels, test_size=0.30, random_state=42, stratify=labels
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.50, random_state=42, stratify=y_temp
    )
    print(f"\nSplit — train: {len(X_train)}, val: {len(X_val)}, test: {len(X_test)}")

    models = make_models()

    # 3. 5-fold CV on training set
    print("\n── 5-fold cross-validation (training set) ──")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_results = {}
    for name, pipe in models.items():
        scores = cross_val_score(pipe, X_train, y_train, cv=cv, scoring="f1_macro", n_jobs=-1)
        cv_results[name] = {
            "cv_macro_f1_mean": round(float(scores.mean()), 4),
            "cv_macro_f1_std": round(float(scores.std()), 4),
        }
        print(f"  {name}: {scores.mean():.4f} ± {scores.std():.4f}")

    # 4. Fit all models, pick best on validation set
    print("\n── Validation set ──")
    val_scores = {}
    for name, pipe in models.items():
        pipe.fit(X_train, y_train)
        val_scores[name] = float(f1_score(pipe.predict(X_val), y_val, average="macro"))
        print(f"  {name}: macro-F1 = {val_scores[name]:.4f}")

    best_name = max(val_scores, key=val_scores.__getitem__)
    print(f"\nWinner: {best_name} (val macro-F1 = {val_scores[best_name]:.4f})")

    # 5. Re-fit winner on train+val, evaluate on held-out test set
    winner = models[best_name]
    winner.fit(X_train + X_val, y_train + y_val)
    test_metrics = evaluate(winner, X_test, y_test, "Test set (held-out, looked at once)")

    # 6. Top predictive features (LogReg / NB)
    top_features: dict = {}
    if best_name in ("logistic_regression", "naive_bayes"):
        vocab = winner.named_steps["tfidf"].get_feature_names_out()
        clf = winner.named_steps["clf"]
        if hasattr(clf, "coef_"):
            for i, cls in enumerate(clf.classes_):
                top_idx = np.argsort(clf.coef_[i])[-12:][::-1]
                top_features[cls] = [vocab[j] for j in top_idx]

    # 7. Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(winner, OUTPUT_PATH)
    print(f"\nSaved: {OUTPUT_PATH}")

    metrics = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "model": best_name,
        "datasets": ["tatsu-lab/alpaca (~40k)", "databricks/databricks-dolly-15k (~15k)"],
        "total_samples": total,
        "label_distribution": {k: int(v) for k, v in dist.items()},
        "split": {"train": len(X_train), "val": len(X_val), "test": len(X_test)},
        "cv_results": cv_results,
        "val_macro_f1_per_model": {k: round(v, 4) for k, v in val_scores.items()},
        "test_metrics": test_metrics,
        "top_features_per_class": top_features,
    }

    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Saved: {METRICS_PATH}")

    print(f"\n── Final ──")
    print(f"  Model:       {best_name}")
    print(f"  Weighted F1: {test_metrics['weighted_f1']}")
    print(f"  Macro F1:    {test_metrics['macro_f1']}")


if __name__ == "__main__":
    main()
