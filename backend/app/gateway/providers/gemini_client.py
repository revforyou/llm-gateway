import time
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.core.config import settings
from app.gateway.providers.groq_client import CompletionResult, ProviderError


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
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
        f":generateContent?key={settings.gemini_api_key}"
    )
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens},
    }

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            latency_ms = int((time.monotonic() - start) * 1000)
            data = r.json()
            candidate = data["candidates"][0]
            content = candidate["content"]["parts"][0]["text"]
            usage = data.get("usageMetadata", {})
            return CompletionResult(
                content=content,
                tokens_in=usage.get("promptTokenCount", 0),
                tokens_out=usage.get("candidatesTokenCount", 0),
                finish_reason=candidate.get("finishReason", "STOP"),
                latency_ms=latency_ms,
            )
    except httpx.HTTPStatusError as e:
        raise ProviderError(f"Gemini error {e.response.status_code}: {e.response.text}") from e
    except Exception as e:
        raise ProviderError(f"Gemini request failed: {e}") from e
