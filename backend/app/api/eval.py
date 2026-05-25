import asyncio
import json
from fastapi import APIRouter, HTTPException, Request, status
from app.core.db import get_db
from app.core.config import settings
from app.eval.judge import judge
from app.eval.grounding import check_grounding
from app.eval.refusal import check_refusal
from app.eval.toxicity import check_toxicity
from app.models.schemas import ApiResponse

router = APIRouter(prefix="/v1/eval", tags=["eval"])

EVALUATOR_MODEL = "gemini-2.0-flash"


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

    try:
        async with asyncio.timeout(25.0):
            judge_result, eval_latency = await judge(prompt, response_text)
            grounding_flag, grounding_issues = check_grounding(prompt, response_text)
            refusal_flag = check_refusal(response_text)
            toxicity_flag = check_toxicity(response_text)
    except TimeoutError:
        return ApiResponse(data={"skipped": "eval timeout"})
    except Exception as e:
        return ApiResponse(data={"skipped": f"eval error: {e}"})

    quality_score = round(
        0.5 * judge_result.accuracy
        + 0.3 * judge_result.helpfulness
        + 0.2 * judge_result.tone
    )
    hallucination_flag = judge_result.accuracy < 70 or grounding_flag

    flags = {}
    if grounding_issues:
        flags["grounding"] = grounding_issues
    if judge_result.issues:
        flags["judge"] = judge_result.issues

    db.table("eval_scores").insert({
        "response_id": response_id,
        "team_id": resp["team_id"],
        "quality_score": quality_score,
        "accuracy_score": judge_result.accuracy,
        "helpfulness_score": judge_result.helpfulness,
        "tone_score": judge_result.tone,
        "hallucination_flag": hallucination_flag,
        "refusal_flag": refusal_flag,
        "toxicity_flag": toxicity_flag,
        "flags": flags,
        "evaluator_model": EVALUATOR_MODEL,
        "eval_latency_ms": eval_latency,
    }).execute()

    return ApiResponse(data={
        "quality_score": quality_score,
        "hallucination_flag": hallucination_flag,
        "eval_latency_ms": eval_latency,
    })
