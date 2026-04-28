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


def route(complexity: str, team_overrides: dict | None = None) -> dict:
    config = COMPLEXITY_ROUTES.get(complexity, COMPLEXITY_ROUTES["medium"]).copy()
    if team_overrides:
        config.update(team_overrides)
    return config
