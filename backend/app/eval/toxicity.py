TOXIC_WORDS = {
    "idiot", "stupid", "moron", "dumb", "shut up", "go away",
    "hate you", "worthless", "useless", "incompetent",
}


def check_toxicity(response: str) -> bool:
    response_lower = response.lower()
    return any(w in response_lower for w in TOXIC_WORDS)
