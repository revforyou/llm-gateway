import secrets
import hashlib
import hmac
import bcrypt


def generate_api_key(env: str = "live") -> tuple[str, str, str]:
    raw = secrets.token_urlsafe(24)
    plaintext = f"sk_{env}_{raw}"
    prefix = plaintext[:12]
    hashed = bcrypt.hashpw(plaintext.encode(), bcrypt.gensalt(rounds=10)).decode()
    return plaintext, prefix, hashed


def verify_key(plaintext: str, hashed: str) -> bool:
    return bcrypt.checkpw(plaintext.encode(), hashed.encode())


def hmac_sign(secret: str, payload: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def hmac_verify(secret: str, payload: str, signature: str) -> bool:
    expected = hmac_sign(secret, payload)
    return hmac.compare_digest(expected, signature)
