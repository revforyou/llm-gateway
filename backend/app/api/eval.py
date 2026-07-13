import json

from fastapi import APIRouter, HTTPException, Request, status

# Re-exported so existing imports (tests, callers) keep working after the eval
# logic moved to app/eval/runner.py.
from app.eval.runner import (
    AGENTIC_EVALUATOR_MODEL,
    EVALUATOR_MODEL,
    agentic_judge_confidence,
    evaluate_response,
)
from app.models.schemas import ApiResponse

__all__ = [
    "router",
    "agentic_judge_confidence",
    "evaluate_response",
    "EVALUATOR_MODEL",
    "AGENTIC_EVALUATOR_MODEL",
]

router = APIRouter(prefix="/v1/eval", tags=["eval"])


@router.post("/run", response_model=ApiResponse)
async def run_eval(request: Request) -> ApiResponse:
    # Kept so the daily backfill job can trigger evals for missed responses over
    # HTTP. The main chat path evaluates in-process (see app/api/chat.py) and does
    # not call this endpoint.
    body_bytes = await request.body()

    try:
        payload = json.loads(body_bytes)
        response_id = payload["response_id"]
    except (json.JSONDecodeError, KeyError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload")

    result = await evaluate_response(response_id)
    return ApiResponse(data=result)
