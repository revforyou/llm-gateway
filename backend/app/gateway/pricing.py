from decimal import Decimal

# Verified pricing 2026-04-28 from provider docs (Developer-tier rates).
# Free tier actual cost = $0; these are attributed costs for dashboard display.
MODEL_PRICING: dict[str, dict[str, float]] = {
    "groq:llama-3.1-8b-instant": {"in": 0.05, "out": 0.08},
    "groq:llama-3.3-70b-versatile": {"in": 0.59, "out": 0.79},
    "gemini:gemini-2.5-flash-lite": {"in": 0.10, "out": 0.40},
}


def calc_cost(provider: str, model: str, tokens_in: int, tokens_out: int) -> Decimal:
    key = f"{provider}:{model}"
    p = MODEL_PRICING.get(key, {"in": 0.0, "out": 0.0})
    cost_in = Decimal(tokens_in) * Decimal(str(p["in"])) / Decimal(1_000_000)
    cost_out = Decimal(tokens_out) * Decimal(str(p["out"])) / Decimal(1_000_000)
    return cost_in + cost_out
