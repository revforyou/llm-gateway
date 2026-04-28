from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    env: str = "development"
    app_base_url: str = "http://localhost:8000"

    groq_api_key: str
    gemini_api_key: str

    supabase_url: str
    supabase_service_key: str
    supabase_anon_key: str

    redis_url: str

    qstash_token: str
    qstash_current_signing_key: str
    qstash_next_signing_key: str

    eval_sample_rate: float = 0.85
    traffic_burst_size: int = 12

    internal_cron_secret: str
    alert_webhook_url: str = ""
    alert_webhook_secret: str = ""

    sentry_dsn: str = ""
    demo_team_id: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
