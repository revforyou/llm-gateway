import time
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.core.config import settings


class ProviderError(Exception):
    pass


class CompletionResult:
    def __init__(self, content: str, tokens_in: int, tokens_out: int,
                 finish_reason: str, latency_ms: int):
        self.content = content
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.finish_reason = finish_reason
        self.latency_ms = latency_ms


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
    reraise=True,
)
async def complete(
    model: str,
    system: str,
    prompt: str,
    max_tokens: int = 512,
) -> CompletionResult:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
    }

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            latency_ms = int((time.monotonic() - start) * 1000)
            data = r.json()
            choice = data["choices"][0]
            usage = data["usage"]
            return CompletionResult(
                content=choice["message"]["content"],
                tokens_in=usage["prompt_tokens"],
                tokens_out=usage["completion_tokens"],
                finish_reason=choice["finish_reason"],
                latency_ms=latency_ms,
            )
    except httpx.HTTPStatusError as e:
        raise ProviderError(f"Groq error {e.response.status_code}: {e.response.text}") from e
    except Exception as e:
        raise ProviderError(f"Groq request failed: {e}") from e
