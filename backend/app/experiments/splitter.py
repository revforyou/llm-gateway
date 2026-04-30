import hashlib


def assign_variant(experiment_id: str, request_key: str, traffic_split: float) -> str:
    h = hashlib.sha256(f"{experiment_id}:{request_key}".encode()).hexdigest()
    bucket = int(h[:8], 16) / 0xFFFFFFFF  # uniform [0, 1)
    return "a" if bucket < traffic_split else "b"
