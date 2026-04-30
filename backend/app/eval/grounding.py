"""Entity grounding check — flags if response introduces entities not in the prompt."""
import re

ENTITY_PATTERNS = [
    re.compile(r"\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b"),   # numbers
    re.compile(r"\$[\d,]+(?:\.\d+)?"),                   # dollar amounts
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),         # dates
    re.compile(r"\b[A-Z]{2,}\b"),                        # ALL-CAPS words
    re.compile(r"https?://\S+"),                         # URLs
]

HEDGE_WORDS = {"definitely", "guaranteed", "always", "never", "100%", "absolutely"}


def check_grounding(prompt: str, response: str) -> tuple[bool, list[str]]:
    """Returns (hallucination_flag, list_of_issues)."""
    issues = []

    prompt_entities: set[str] = set()
    for pat in ENTITY_PATTERNS:
        prompt_entities.update(pat.findall(prompt))

    response_entities: set[str] = set()
    for pat in ENTITY_PATTERNS:
        response_entities.update(pat.findall(response))

    new_entities = response_entities - prompt_entities
    if len(new_entities) >= 2:
        issues.append(f"introduced_entities:{list(new_entities)[:3]}")

    response_lower = response.lower()
    found_hedges = [w for w in HEDGE_WORDS if w in response_lower]
    if found_hedges:
        issues.append(f"overconfident_language:{found_hedges}")

    hallucination_flag = len(new_entities) >= 2
    return hallucination_flag, issues
