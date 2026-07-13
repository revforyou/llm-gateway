"""Set required env vars before any module-level imports run.

Uses os.environ directly (not setdefault) so that empty strings
passed by CI when secrets are unset get overridden with test values.
"""
import os

_DEFAULTS = {
    "GROQ_API_KEY": "test-groq-key",
    "GEMINI_API_KEY": "test-gemini-key",
    "SUPABASE_URL": "http://localhost:54321",
    "SUPABASE_SERVICE_KEY": "test-service-key",
    "SUPABASE_ANON_KEY": "test-anon-key",
    "REDIS_URL": "redis://localhost:6379",
    "INTERNAL_CRON_SECRET": "test-cron-secret",
    "APP_BASE_URL": "http://localhost:8000",
}

for k, v in _DEFAULTS.items():
    # Override if missing OR empty (CI sets empty string when secret not configured)
    if not os.environ.get(k):
        os.environ[k] = v
