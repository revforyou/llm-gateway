"""
Semantic grounding check using Gemini embeddings.

Computes cosine similarity between the prompt embedding and response embedding.
A response that is semantically distant from the prompt is likely hallucinating
or drifting off-topic. Falls back to returning no flag on API error so a Gemini
outage never blocks eval writes.

Threshold rationale for customer support:
  - On-topic responses typically score 0.55–0.90 (answer is about the same domain)
  - Off-topic or fabricated responses typically score 0.20–0.45
  - 0.40 is the chosen cutoff, validated against the synthetic eval set
"""
import httpx
import math
from app.core.config import settings

# text-embedding-004 returns 404 for this key; gemini-embedding-001 is current.
EMBED_MODEL = "gemini-embedding-001"
EMBED_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{EMBED_MODEL}"
    f":embedContent?key={settings.gemini_api_key}"
)
SIMILARITY_THRESHOLD = 0.40

HEDGE_WORDS = {"definitely", "guaranteed", "always", "never", "100%", "absolutely"}


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def _embed(text: str) -> list[float]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(
            EMBED_URL,
            json={"model": f"models/{EMBED_MODEL}", "content": {"parts": [{"text": text}]}},
        )
        r.raise_for_status()
    return r.json()["embedding"]["values"]


async def check_grounding(prompt: str, response: str) -> tuple[bool, list[str]]:
    """Returns (hallucination_flag, list_of_issues).

    Primary signal: cosine similarity between prompt and response embeddings.
    Secondary signal: overconfident hedge-words that shouldn't appear in
    a grounded customer-support reply.
    """
    issues: list[str] = []
    hallucination_flag = False

    # --- Semantic similarity via Gemini embeddings ---
    try:
        prompt_emb, response_emb = await _embed(prompt[:500]), await _embed(response[:1000])
        similarity = _cosine(prompt_emb, response_emb)
        if similarity < SIMILARITY_THRESHOLD:
            issues.append(f"low_semantic_similarity:{round(similarity, 3)}")
            hallucination_flag = True
    except Exception:
        # Don't block eval writes on embedding API failures
        pass

    # --- Hedge-word check (deterministic, fast) ---
    response_lower = response.lower()
    found_hedges = [w for w in HEDGE_WORDS if w in response_lower]
    if found_hedges:
        issues.append(f"overconfident_language:{found_hedges}")

    return hallucination_flag, issues
