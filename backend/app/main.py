import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api import health, chat, keys, metrics, internal, eval, experiments

if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1)

app = FastAPI(title="LLM Gateway", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Cron-Secret"],
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(keys.router)
app.include_router(metrics.router)
app.include_router(internal.router)
app.include_router(eval.router)
app.include_router(experiments.router)
