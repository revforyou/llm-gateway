"""LangGraph reflection-loop eval pipeline: judge -> conditional critic -> aggregate.

Unlike the classic single-shot judge (app/eval/judge.py), this models evaluation as
two cooperating agents instead of one call: a judge scores the response and reports
its own confidence, and — only when that confidence is low or the accuracy score is
low enough to suggest a hallucination — a second, independent critic re-examines the
same response before the score is finalized. Most evals never touch the critic node;
it exists for the borderline cases where a single-shot judge is least reliable.
"""
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.eval.agentic.state import EvalState

JUDGE_MODEL = "gemini-2.5-flash-lite"

# Confidence below this, or an accuracy score below this, routes to the critic
# instead of finalizing the judge's score directly.
CONFIDENCE_THRESHOLD = 0.7
ACCURACY_REVIEW_THRESHOLD = 65


class JudgeScore(BaseModel):
    accuracy: int = Field(ge=0, le=100, description="Factual correctness")
    helpfulness: int = Field(ge=0, le=100, description="Does it solve the user's problem")
    tone: int = Field(ge=0, le=100, description="Professional and empathetic")
    reasoning: str = Field(description="One short sentence")
    issues: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1, description="Judge's own confidence in this score")


class CriticVerdict(BaseModel):
    agrees_with_judge: bool
    revised_accuracy: int = Field(ge=0, le=100)
    revised_helpfulness: int = Field(ge=0, le=100)
    revised_tone: int = Field(ge=0, le=100)
    notes: str = Field(description="One short sentence explaining the verdict")


JUDGE_PROMPT = """You are an evaluator of customer-support AI responses. Score on a 0-100 scale.

INPUT TICKET:
{prompt}

AI RESPONSE TO EVALUATE:
{response}

Scoring guidance:
- Technically correct but unhelpful: 60-70 helpfulness
- Fabricates details: <50 accuracy
- Excellent responses: 85-95 across the board
- Reserve 95-100 for truly outstanding responses

Also report your own confidence (0-1) in this score. Use a low confidence when the
ticket is ambiguous, the response is borderline, or you are not sure the response is
fully grounded in the ticket."""

CRITIC_PROMPT = """You are a second-opinion reviewer auditing another evaluator's score of a
customer-support AI response. The first evaluator flagged low confidence or low accuracy on
this one — independently check their work rather than deferring to it.

INPUT TICKET:
{prompt}

AI RESPONSE TO EVALUATE:
{response}

FIRST EVALUATOR'S SCORE:
accuracy={accuracy}, helpfulness={helpfulness}, tone={tone}
reasoning: {reasoning}

Score the response yourself. If you agree with the first evaluator, set
agrees_with_judge=true and echo their scores back as the revised_* fields. If you
disagree, set agrees_with_judge=false and give corrected revised_* scores."""


def _client(max_output_tokens: int) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=JUDGE_MODEL,
        google_api_key=settings.gemini_api_key,
        temperature=0.1,
        max_output_tokens=max_output_tokens,
    )


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=5))
async def judge_node(state: EvalState) -> dict:
    llm = _client(300).with_structured_output(JudgeScore)
    result: JudgeScore = await llm.ainvoke(
        JUDGE_PROMPT.format(prompt=state["prompt"], response=state["response"])
    )
    return {
        "accuracy": result.accuracy,
        "helpfulness": result.helpfulness,
        "tone": result.tone,
        "reasoning": result.reasoning,
        "issues": result.issues,
        "judge_confidence": result.confidence,
    }


def route_after_judge(state: EvalState) -> str:
    if (
        state["judge_confidence"] < CONFIDENCE_THRESHOLD
        or state["accuracy"] < ACCURACY_REVIEW_THRESHOLD
    ):
        return "critic"
    return "aggregate"


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=5))
async def critic_node(state: EvalState) -> dict:
    llm = _client(200).with_structured_output(CriticVerdict)
    verdict: CriticVerdict = await llm.ainvoke(
        CRITIC_PROMPT.format(
            prompt=state["prompt"],
            response=state["response"],
            accuracy=state["accuracy"],
            helpfulness=state["helpfulness"],
            tone=state["tone"],
            reasoning=state["reasoning"],
        )
    )
    update: dict = {
        "critic_verdict": "confirmed" if verdict.agrees_with_judge else "revised",
        "critic_notes": verdict.notes,
        "reviewed_by_critic": True,
    }
    if not verdict.agrees_with_judge:
        update["accuracy"] = verdict.revised_accuracy
        update["helpfulness"] = verdict.revised_helpfulness
        update["tone"] = verdict.revised_tone
    return update


def aggregate_node(state: EvalState) -> dict:
    quality = round(0.5 * state["accuracy"] + 0.3 * state["helpfulness"] + 0.2 * state["tone"])
    return {"quality_score": quality}


def build_graph():
    graph = StateGraph(EvalState)
    graph.add_node("judge", judge_node)
    graph.add_node("critic", critic_node)
    graph.add_node("aggregate", aggregate_node)
    graph.add_edge(START, "judge")
    graph.add_conditional_edges(
        "judge", route_after_judge, {"critic": "critic", "aggregate": "aggregate"}
    )
    graph.add_edge("critic", "aggregate")
    graph.add_edge("aggregate", END)
    return graph.compile()


_compiled_graph = build_graph()


class AgenticEvalResult(BaseModel):
    quality_score: int
    accuracy: int
    helpfulness: int
    tone: int
    reasoning: str
    issues: list[str]
    judge_confidence: float
    reviewed_by_critic: bool
    critic_verdict: str | None = None
    critic_notes: str | None = None


async def run_agentic_eval(prompt: str, response: str) -> AgenticEvalResult:
    """Runs the judge -> conditional critic -> aggregate graph and returns final scores."""
    final_state = await _compiled_graph.ainvoke({
        "prompt": prompt[:500],
        "response": response[:1000],
        "issues": [],
        "reviewed_by_critic": False,
    })
    return AgenticEvalResult(
        quality_score=final_state["quality_score"],
        accuracy=final_state["accuracy"],
        helpfulness=final_state["helpfulness"],
        tone=final_state["tone"],
        reasoning=final_state["reasoning"],
        issues=final_state["issues"],
        judge_confidence=final_state["judge_confidence"],
        reviewed_by_critic=final_state["reviewed_by_critic"],
        critic_verdict=final_state.get("critic_verdict"),
        critic_notes=final_state.get("critic_notes"),
    )
