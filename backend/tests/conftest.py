"""Set required env vars before any module-level imports run."""
import os

_DEFAULTS = {
    "GROQ_API_KEY": "test-groq-key",
    "GEMINI_API_KEY": "test-gemini-key",
    "SUPABASE_URL": "http://localhost:54321",
    "SUPABASE_SERVICE_KEY": "test-service-key",
    "SUPABASE_ANON_KEY": "test-anon-key",
    "REDIS_URL": "redis://localhost:6379",
    "QSTASH_TOKEN": "test-qstash-token",
    "QSTASH_CURRENT_SIGNING_KEY": "test-sig-current",
    "QSTASH_NEXT_SIGNING_KEY": "test-sig-next",
    "INTERNAL_CRON_SECRET": "test-cron-secret",
    "APP_BASE_URL": "http://localhost:8000",
}

for k, v in _DEFAULTS.items():
    os.environ.setdefault(k, v)
