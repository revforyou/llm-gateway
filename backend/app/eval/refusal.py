import re

REFUSAL_PATTERNS = re.compile(
    r"\b(I cannot|I can't|I'm not able|I am unable|as an AI|"
    r"I don't have access|I don't have the ability|I'm just an AI|"
    r"I'm unable to|not able to assist)\b",
    re.IGNORECASE,
)


def check_refusal(response: str) -> bool:
    return bool(REFUSAL_PATTERNS.search(response))
