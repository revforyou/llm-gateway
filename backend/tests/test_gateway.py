import pytest
from app.gateway.classifier import _rule_based_classify, _is_complex
from app.gateway.router import route
from app.gateway.pricing import calc_cost
from decimal import Decimal


def test_simple_classification():
    text = "How do I reset my password?"
    complexity, score = _rule_based_classify(text)
    assert complexity == "simple"
    assert score > 0.5


def test_complex_classification_escalation():
    text = "I want to speak to a manager about the fraud on my account immediately."
    assert _is_complex(text) is True


def test_complex_classification_length():
    text = "x" * 900
    assert _is_complex(text) is True


def test_medium_classification():
    text = "I need help understanding my invoice from last month."
    complexity, score = _rule_based_classify(text)
    assert complexity == "medium"


def test_router_simple():
    config = route("simple")
    assert config["model"] == "llama-3.1-8b-instant"
    assert config["provider"] == "groq"


def test_router_complex():
    config = route("complex")
    assert config["model"] == "llama-3.3-70b-versatile"
    assert config["max_tokens"] >= 512


def test_pricing_simple():
    cost = calc_cost("groq", "llama-3.1-8b-instant", 100, 50)
    assert isinstance(cost, Decimal)
    assert cost > 0


def test_pricing_zero_tokens():
    cost = calc_cost("groq", "llama-3.1-8b-instant", 0, 0)
    assert cost == Decimal("0")


def test_pricing_unknown_model():
    cost = calc_cost("groq", "unknown-model", 1000, 500)
    assert cost == Decimal("0")
