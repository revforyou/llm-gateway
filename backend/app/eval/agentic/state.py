"""Shared state passed between nodes in the reflection-loop eval graph."""
from typing import TypedDict


class EvalState(TypedDict, total=False):
    prompt: str
    response: str
    accuracy: int
    helpfulness: int
    tone: int
    reasoning: str
    issues: list[str]
    judge_confidence: float
    reviewed_by_critic: bool
    critic_verdict: str  # "confirmed" | "revised" — present only if critic ran
    critic_notes: str
    quality_score: int
