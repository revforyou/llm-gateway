import asyncio
import json
import random
import time

from fastapi import APIRouter, HTTPException, Request, status

from app.core.config import settings
from app.core.db import get_db
from app.eval.agentic import run_agentic_eval
from app.eval.grounding import check_grounding
from app.eval.judge import judge
from app.eval.refusal import check_refusal
from app.eval.toxicity import check_toxicity
from app.models.schemas import ApiResponse

router = APIRouter(prefix="/v1/eval", tags=["eval"])

EVALUATOR_MODEL = "gemini-2.5-flash-lite"
AGENTIC_EVALUATOR_MODEL = "gemini-2.5-flash-lite+langgraph-reflection"

# Raw judge confidence at/above this is trusted without a critic pass. Mirrors
# the CONFIDENCE_THRESHOLD the graph itself uses to route to the critic.
JUDGE_CONFIDENCE_TRUST_THRESHOLD = 0.7


def agentic_judge_confidence(reviewed_by_critic: bool, raw_confidence: float) -> str:
    """Map an agentic eval to the eval_scores.judge_confidence enum ("high"|"low").

    The column means "trust these numbers?" — downstream consumers (metrics
    dashboard, retrain job) drop "low" rows. An agentic score is trustworthy when
    the critic vetted it OR the raw judge was already confident; the raw pre-critic
    score is preserved separately in flags. Writing "low" for a critic-reviewed row
    would wrongly discard exactly the corrections the reflection loop exists to make.
    """
    if reviewed_by_critic or raw_confidence >= JUDGE_CONFIDENCE_TRUST_THRESHOLD:
        return "high"
    return "low"


@router.post("/run", response_model=ApiResponse)
async def run_eval(request: Request) -> ApiResponse:
    # QStash v2 sends a JWT in upstash-signature — we trust the delivery
    # since the endpoint URL is only known to QStash and not publicly documented.
    body_bytes = await request.body()

    try:
        payload = json.loads(body_bytes)
        response_id = payload["response_id"]
    except (json.JSONDecodeError, KeyError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload")

    db = get_db()

    resp_row = (
        db.table("responses")
        .select("id, request_id, team_id, content")
        .eq("id", response_id)
        .maybe_single()
        .execute()
    )
    if not resp_row or not resp_row.data:
        return ApiResponse(data={"skipped": "response not found"})

    resp = resp_row.data
    req_row = (
        db.table("requests")
        .select("prompt, team_id")
        .eq("id", resp["request_id"])
        .maybe_single()
        .execute()
    )
    if not req_row or not req_row.data:
        return ApiResponse(data={"skipped": "request not found"})

    prompt = req_row.data["prompt"]
    response_text = resp["content"]

    # A sampled fraction of evals run through the LangGraph judge -> conditional
    # critic -> aggregate pipeline instead of the classic single-shot judge, so the
    # reflection loop is genuinely exercised in production, not just demo code.
    use_agentic = random.random() < settings.agentic_eval_sample_rate

    try:
        async with asyncio.timeout(35.0):
            if use_agentic:
                start = time.monotonic()
                agentic_result = await run_agentic_eval(prompt, response_text)
                eval_latency = int((time.monotonic() - start) * 1000)
                accuracy, helpfulness, tone = (
                    agentic_result.accuracy,
                    agentic_result.helpfulness,
                    agentic_result.tone,
                )
                quality_score = agentic_result.quality_score
                judge_issues = agentic_result.issues
                judge_confidence = agentic_judge_confidence(
                    agentic_result.reviewed_by_critic, agentic_result.judge_confidence
                )
                evaluator_model = AGENTIC_EVALUATOR_MODEL
                agentic_flags = {
                    "reviewed_by_critic": agentic_result.reviewed_by_critic,
                    "judge_confidence_raw": agentic_result.judge_confidence,
                }
                if agentic_result.critic_verdict:
                    agentic_flags["critic_verdict"] = agentic_result.critic_verdict
                    agentic_flags["critic_notes"] = agentic_result.critic_notes
            else:
                judge_result, eval_latency = await judge(prompt, response_text)
                accuracy, helpfulness, tone = (
                    judge_result.accuracy,
                    judge_result.helpfulness,
                    judge_result.tone,
                )
                quality_score = round(0.5 * accuracy + 0.3 * helpfulness + 0.2 * tone)
                judge_issues = judge_result.issues
                judge_confidence = judge_result.confidence  # "high" | "low"
                evaluator_model = EVALUATOR_MODEL
                agentic_flags = None

            grounding_flag, grounding_issues = await check_grounding(prompt, response_text)
            refusal_flag = check_refusal(response_text)
            toxicity_flag = check_toxicity(response_text)
    except TimeoutError:
        return ApiResponse(data={"skipped": "eval timeout"})
    except Exception as e:
        return ApiResponse(data={"skipped": f"eval error: {e}"})

    hallucination_flag = accuracy < 70 or grounding_flag

    flags = {}
    if grounding_issues:
        flags["grounding"] = grounding_issues
    if judge_issues:
        flags["judge"] = judge_issues
    if judge_confidence == "low" and not use_agentic:
        flags["judge_parse_failed"] = True
    if agentic_flags is not None:
        flags["agentic"] = agentic_flags

    db.table("eval_scores").insert({
        "response_id": response_id,
        "team_id": resp["team_id"],
        "quality_score": quality_score,
        "accuracy_score": accuracy,
        "helpfulness_score": helpfulness,
        "tone_score": tone,
        "hallucination_flag": hallucination_flag,
        "refusal_flag": refusal_flag,
        "toxicity_flag": toxicity_flag,
        "flags": flags,
        "judge_confidence": judge_confidence,
        "evaluator_model": evaluator_model,
        "eval_latency_ms": eval_latency,
    }).execute()

    return ApiResponse(data={
        "quality_score": quality_score,
        "hallucination_flag": hallucination_flag,
        "eval_latency_ms": eval_latency,
    })
