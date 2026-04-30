import pytest
from app.experiments.stats import welch_test
from app.experiments.splitter import assign_variant


def test_welch_known_values():
    # Two clearly different distributions — should be significant
    scores_a = [80.0] * 50
    scores_b = [90.0] * 50
    result = welch_test(scores_a, scores_b)
    assert result["significant"] is True
    assert result["p_value"] < 0.05
    assert result["effect_size"] == pytest.approx(10.0, abs=0.1)
    assert result["mean_a"] == pytest.approx(80.0)
    assert result["mean_b"] == pytest.approx(90.0)


def test_welch_not_significant():
    # Same distribution — should not be significant
    scores_a = [85.0] * 50
    scores_b = [85.0] * 50
    result = welch_test(scores_a, scores_b)
    assert result["significant"] is False


def test_welch_insufficient_data():
    result = welch_test([80.0], [90.0])
    assert result["significant"] is False
    assert result["p_value"] is None


def test_splitter_deterministic():
    exp_id = "test-experiment-abc"
    key = "request-key-123"
    v1 = assign_variant(exp_id, key, 0.5)
    v2 = assign_variant(exp_id, key, 0.5)
    assert v1 == v2  # same inputs → same output every time


def test_splitter_distribution():
    # With 1000 requests, should be ~50/50 within 5%
    exp_id = "distribution-test"
    a_count = sum(
        1 for i in range(1000)
        if assign_variant(exp_id, f"req-{i}", 0.5) == "a"
    )
    assert 450 <= a_count <= 550


def test_splitter_traffic_split_70():
    exp_id = "split-70-test"
    a_count = sum(
        1 for i in range(1000)
        if assign_variant(exp_id, f"req-{i}", 0.7) == "a"
    )
    assert 650 <= a_count <= 750
