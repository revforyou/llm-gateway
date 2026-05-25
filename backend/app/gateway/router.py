COMPLEXITY_ROUTES: dict[str, dict] = {
    "simple": {
        "provider": "groq",
        "model": "llama-3.1-8b-instant",
        "max_tokens": 256,
        "prompt_version": "v1_vanilla",
    },
    "medium": {
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "max_tokens": 512,
        "prompt_version": "v1_vanilla",
    },
    "complex": {
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "max_tokens": 1024,
        "prompt_version": "v1_vanilla",
    },
}


CONFIDENCE_THRESHOLDS = {
    # Only route to the cheaper model when the classifier is confident enough.
    # Below threshold: upgrade to the next tier to avoid misroutes.
    "simple": 0.75,   # P(simple) < 0.75 → treat as medium
    "medium": 0.65,   # P(medium) < 0.65 → treat as complex
}


def route(complexity: str, score: float = 1.0, team_overrides: dict | None = None) -> dict:
    # Confidence gating: uncertain classifications route to the safer (better) model
    threshold = CONFIDENCE_THRESHOLDS.get(complexity)
    if threshold and score < threshold:
        upgrade = {"simple": "medium", "medium": "complex"}
        complexity = upgrade.get(complexity, complexity)

    config = COMPLEXITY_ROUTES.get(complexity, COMPLEXITY_ROUTES["medium"]).copy()
    if team_overrides:
        config.update(team_overrides)
    return config
