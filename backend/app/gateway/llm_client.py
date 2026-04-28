from app.gateway.providers import groq_client, gemini_client
from app.gateway.providers.groq_client import CompletionResult, ProviderError

__all__ = ["complete", "CompletionResult", "ProviderError"]

SYSTEM_PROMPTS = {
    "v1_vanilla": "You are a helpful assistant. Answer the user's question.",
    "v2_tuned_support": (
        "You are a customer support specialist for SaaS products. For every ticket:\n"
        "1. Acknowledge the issue in one sentence.\n"
        "2. Provide the answer or next steps in numbered form (max 4 steps).\n"
        "3. End with a single offer to escalate if needed.\n\n"
        "Rules:\n"
        "- If unsure, say \"I'd recommend escalating this — let me connect you with someone "
        "who can help\" rather than guessing.\n"
        "- Never invent product features, policies, prices, or timelines.\n"
        "- Keep total response under 120 words."
    ),
}


async def complete(
    provider: str,
    model: str,
    prompt: str,
    prompt_version: str = "v1_vanilla",
    max_tokens: int = 512,
) -> CompletionResult:
    system = SYSTEM_PROMPTS.get(prompt_version, SYSTEM_PROMPTS["v1_vanilla"])
    if provider == "groq":
        return await groq_client.complete(model, system, prompt, max_tokens)
    elif provider == "gemini":
        return await gemini_client.complete(model, system, prompt, max_tokens)
    raise ProviderError(f"Unknown provider: {provider}")
