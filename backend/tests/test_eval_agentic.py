from app.api.eval import agentic_judge_confidence
from app.eval.agentic import graph as agentic_graph
from app.eval.agentic.graph import (
    CriticVerdict,
    JudgeScore,
    aggregate_node,
    build_graph,
    route_after_judge,
)


def test_critic_reviewed_row_is_trusted_even_when_raw_confidence_low():
    # The reflection loop's whole point: a low-raw-confidence score that the critic
    # vetted must be marked "high" so metrics/retrain don't discard it.
    assert agentic_judge_confidence(reviewed_by_critic=True, raw_confidence=0.3) == "high"


def test_confident_judge_without_critic_is_trusted():
    assert agentic_judge_confidence(reviewed_by_critic=False, raw_confidence=0.9) == "high"


def test_low_confidence_unreviewed_is_low():
    # Defensive: if routing ever lets a low-confidence row skip the critic, mark it low.
    assert agentic_judge_confidence(reviewed_by_critic=False, raw_confidence=0.3) == "low"


class _FakeStructuredLLM:
    def __init__(self, result):
        self._result = result

    async def ainvoke(self, _prompt):
        return self._result


class _FakeChatModel:
    """Stands in for ChatGoogleGenerativeAI so tests never hit the network."""

    def __init__(self, judge_result=None, critic_result=None):
        self._judge_result = judge_result
        self._critic_result = critic_result

    def with_structured_output(self, schema):
        if schema is JudgeScore:
            return _FakeStructuredLLM(self._judge_result)
        return _FakeStructuredLLM(self._critic_result)


def test_route_after_judge_low_confidence_goes_to_critic():
    state = {"judge_confidence": 0.3, "accuracy": 90}
    assert route_after_judge(state) == "critic"


def test_route_after_judge_low_accuracy_goes_to_critic():
    state = {"judge_confidence": 0.95, "accuracy": 40}
    assert route_after_judge(state) == "critic"


def test_route_after_judge_confident_and_accurate_skips_critic():
    state = {"judge_confidence": 0.9, "accuracy": 85}
    assert route_after_judge(state) == "aggregate"


def test_aggregate_node_matches_composite_formula():
    state = {"accuracy": 80, "helpfulness": 60, "tone": 100}
    result = aggregate_node(state)
    assert result["quality_score"] == round(0.5 * 80 + 0.3 * 60 + 0.2 * 100)


async def test_graph_skips_critic_when_judge_is_confident(monkeypatch):
    judge_result = JudgeScore(
        accuracy=90, helpfulness=88, tone=92, reasoning="solid", issues=[], confidence=0.95
    )
    monkeypatch.setattr(
        agentic_graph, "_client", lambda *_a, **_kw: _FakeChatModel(judge_result=judge_result)
    )

    final_state = await build_graph().ainvoke({
        "prompt": "how do I reset my password",
        "response": "click forgot password",
        "issues": [],
        "reviewed_by_critic": False,
    })

    assert final_state["reviewed_by_critic"] is False
    assert "critic_verdict" not in final_state
    assert final_state["quality_score"] == round(0.5 * 90 + 0.3 * 88 + 0.2 * 92)


async def test_graph_routes_to_critic_and_applies_revision(monkeypatch):
    judge_result = JudgeScore(
        accuracy=30,
        helpfulness=40,
        tone=70,
        reasoning="looks fabricated",
        issues=["hallucination"],
        confidence=0.9,
    )
    critic_result = CriticVerdict(
        agrees_with_judge=False,
        revised_accuracy=10,
        revised_helpfulness=15,
        revised_tone=50,
        notes="confirmed fabrication",
    )
    monkeypatch.setattr(
        agentic_graph,
        "_client",
        lambda *_a, **_kw: _FakeChatModel(judge_result=judge_result, critic_result=critic_result),
    )

    final_state = await build_graph().ainvoke({
        "prompt": "what is your refund policy",
        "response": "guaranteed cash back plus free enterprise upgrade",
        "issues": [],
        "reviewed_by_critic": False,
    })

    assert final_state["reviewed_by_critic"] is True
    assert final_state["critic_verdict"] == "revised"
    assert final_state["accuracy"] == 10
    assert final_state["quality_score"] == round(0.5 * 10 + 0.3 * 15 + 0.2 * 50)


async def test_graph_critic_confirming_keeps_judge_scores(monkeypatch):
    judge_result = JudgeScore(
        accuracy=60, helpfulness=55, tone=65, reasoning="borderline", issues=[], confidence=0.5
    )
    critic_result = CriticVerdict(
        agrees_with_judge=True,
        revised_accuracy=60,
        revised_helpfulness=55,
        revised_tone=65,
        notes="judge got it right",
    )
    monkeypatch.setattr(
        agentic_graph,
        "_client",
        lambda *_a, **_kw: _FakeChatModel(judge_result=judge_result, critic_result=critic_result),
    )

    final_state = await build_graph().ainvoke({
        "prompt": "ambiguous ticket",
        "response": "ambiguous response",
        "issues": [],
        "reviewed_by_critic": False,
    })

    assert final_state["reviewed_by_critic"] is True
    assert final_state["critic_verdict"] == "confirmed"
    assert final_state["accuracy"] == 60  # unchanged — critic agreed, no override applied


async def test_run_agentic_eval_end_to_end(monkeypatch):
    judge_result = JudgeScore(
        accuracy=90, helpfulness=88, tone=92, reasoning="solid", issues=[], confidence=0.95
    )
    monkeypatch.setattr(
        agentic_graph, "_client", lambda *_a, **_kw: _FakeChatModel(judge_result=judge_result)
    )

    result = await agentic_graph.run_agentic_eval("prompt text", "response text")

    assert result.quality_score == round(0.5 * 90 + 0.3 * 88 + 0.2 * 92)
    assert result.reviewed_by_critic is False
    assert result.critic_verdict is None
