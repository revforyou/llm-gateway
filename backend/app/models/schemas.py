from pydantic import BaseModel, Field
from typing import Any
from datetime import datetime


class ChatRequest(BaseModel):
    prompt: str = Field(..., max_length=32768)
    ticket_id: str | None = None


class ChatResponse(BaseModel):
    id: str
    content: str
    model_used: str
    provider: str
    complexity: str
    cost_usd: float
    latency_ms: int
    eval_status: str = "queued"


class CreateKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class CreateKeyResponse(BaseModel):
    id: str
    name: str
    key: str
    prefix: str
    created_at: str


class KeyListItem(BaseModel):
    id: str
    name: str
    prefix: str
    last_used_at: str | None
    created_at: str


class HealthResponse(BaseModel):
    status: str
    db: str
    redis: str
    version: str = "0.1.0"


class MetricsOverview(BaseModel):
    requests_today: int
    avg_quality: float | None
    total_cost_usd: float
    p95_latency_ms: int | None


class ApiResponse(BaseModel):
    data: Any
    error: Any = None
