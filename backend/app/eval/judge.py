"""LLM-as-judge using Gemini 2.5 Flash-Lite. Returns quality scores 0-100."""
import json
import time
import httpx
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential
from app.core.config import settings

JUDGE_SYSTEM = "You are an evaluator of customer-support AI responses."

JUDGE_PROMPT = """You are an evaluator of customer-support AI responses. Score on a 0-100 scale.

INPUT TICKET:
{prompt}

AI RESPONSE TO EVALUATE:
{response}

Return ONLY valid JSON with this exact schema. No prose, no markdown, no code fences:

{{"accuracy": <int 0-100, factual correctness>,
  "helpfulness": <int 0-100, does it actually solve the user's problem>,
  "tone": <int 0-100, professional and empathetic>,
  "reasoning": "<one short sentence>",
  "issues": ["brief tags; empty list if none"]
}}

Scoring guidance:
- Technically correct but unhelpful: 60-70 helpfulness
- Fabricates details: <50 accuracy
- Excellent responses: 85-95 across the board
- Reserve 95-100 for truly outstanding responses"""


class JudgeResult(BaseModel):
    accuracy: int
    helpfulness: int
    tone: int
    reasoning: str
    issues: list[str]


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=5))
async def judge(prompt: str, response: str) -> tuple[JudgeResult, int]:
    model = "gemini-2.5-flash-lite-preview-06-17"
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
        f":generateContent?key={settings.gemini_api_key}"
    )
    user_msg = JUDGE_PROMPT.format(prompt=prompt[:500], response=response[:1000])
    payload = {
        "contents": [{"role": "user", "parts": [{"text": user_msg}]}],
        "generationConfig": {"maxOutputTokens": 300, "temperature": 0.1},
    }

    start = time.monotonic()
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()

    latency_ms = int((time.monotonic() - start) * 1000)
    data = r.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()

    # Strip markdown fences if present
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]

    parsed = json.loads(text)
    result = JudgeResult(
        accuracy=int(parsed.get("accuracy", 70)),
        helpfulness=int(parsed.get("helpfulness", 70)),
        tone=int(parsed.get("tone", 70)),
        reasoning=parsed.get("reasoning", ""),
        issues=parsed.get("issues", []),
    )
    return result, latency_ms
