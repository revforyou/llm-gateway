import hashlib
import random
import time
import asyncio
import httpx
from fastapi import APIRouter, Depends, HTTPException
from app.core.auth import verify_api_key_dep
from app.core.ratelimit import check_rate_limit
from app.core.db import get_db
from app.core.audit import log_audit
from app.core.config import settings
from app.gateway.classifier import classify
from app.gateway.router import route
from app.gateway import llm_client
from app.gateway.providers.groq_client import ProviderError
from app.gateway.pricing import calc_cost
from app.models.schemas import ChatRequest, ChatResponse, ApiResponse

router = APIRouter(prefix="/v1/chat", tags=["chat"])

# Keep strong references to background tasks so they aren't garbage collected
_background_tasks: set = set()


@router.post("", response_model=ApiResponse)
async def chat(
    body: ChatRequest,
    auth: dict = Depends(verify_api_key_dep),
) -> ApiResponse:
    check_rate_limit(auth["key_id"])

    t_start = time.monotonic()

    complexity, complexity_score = classify(body.prompt)
    config = route(complexity)

    try:
        result = await llm_client.complete(
            provider=config["provider"],
            model=config["model"],
            prompt=body.prompt,
            prompt_version=config.get("prompt_version", "v1_vanilla"),
            max_tokens=config.get("max_tokens", 512),
        )
    except ProviderError as e:
        raise HTTPException(status_code=502, detail=f"LLM provider error: {e}")

    total_latency_ms = int((time.monotonic() - t_start) * 1000)
    gateway_overhead_ms = total_latency_ms - result.latency_ms
    cost_usd = float(calc_cost(
        config["provider"], config["model"], result.tokens_in, result.tokens_out
    ))
    prompt_hash = hashlib.sha256(body.prompt.encode()).hexdigest()

    db = get_db()
    req_row = db.table("requests").insert({
        "team_id": auth["team_id"],
        "ticket_id": body.ticket_id,
        "prompt": body.prompt[:2000],
        "prompt_hash": prompt_hash,
        "complexity": complexity,
        "complexity_score": complexity_score,
        "provider": config["provider"],
        "model_used": config["model"],
        "prompt_version": config.get("prompt_version", "v1_vanilla"),
        "tokens_in": result.tokens_in,
        "tokens_out": result.tokens_out,
        "cost_usd": cost_usd,
        "latency_ms": total_latency_ms,
        "gateway_overhead_ms": gateway_overhead_ms,
    }).execute()

    request_id = req_row.data[0]["id"]

    resp_row = db.table("responses").insert({
        "request_id": request_id,
        "team_id": auth["team_id"],
        "content": result.content,
        "finish_reason": result.finish_reason,
    }).execute()

    response_id = resp_row.data[0]["id"]

    task = asyncio.create_task(_enqueue_eval(response_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    log_audit(
        auth["team_id"], auth["key_id"], "chat",
        f"requests/{request_id}",
        {"model": config["model"], "complexity": complexity},
    )

    return ApiResponse(data=ChatResponse(
        id=request_id,
        content=result.content,
        model_used=config["model"],
        provider=config["provider"],
        complexity=complexity,
        cost_usd=cost_usd,
        latency_ms=total_latency_ms,
        eval_status="queued",
    ))


async def _enqueue_eval(response_id: str) -> None:
    if random.random() > settings.eval_sample_rate:
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"https://qstash.upstash.io/v2/publish/{settings.app_base_url}/v1/eval/run",
                headers={"Authorization": f"Bearer {settings.qstash_token}"},
                json={"response_id": response_id},
            )
    except Exception:
        pass
