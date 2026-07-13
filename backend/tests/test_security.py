import pytest
from app.core.security import generate_api_key, verify_key, hmac_sign, hmac_verify


def test_generate_api_key_format():
    plaintext, prefix, hashed = generate_api_key()
    assert plaintext.startswith("sk_live_")
    assert prefix == plaintext[:12]
    assert len(hashed) > 0


def test_generate_api_key_unique():
    _, prefix1, _ = generate_api_key()
    _, prefix2, _ = generate_api_key()
    assert prefix1 != prefix2


def test_verify_key_correct():
    plaintext, _, hashed = generate_api_key()
    assert verify_key(plaintext, hashed) is True


def test_verify_key_wrong():
    _, _, hashed = generate_api_key()
    assert verify_key("sk_live_wrongkey12345678", hashed) is False


def test_plaintext_not_stored_in_hash():
    plaintext, _, hashed = generate_api_key()
    assert plaintext not in hashed


def test_hmac_sign_and_verify():
    secret = "test-secret-key"
    payload = '{"response_id": "abc123"}'
    sig = hmac_sign(secret, payload)
    assert hmac_verify(secret, payload, sig) is True


def test_hmac_verify_wrong_sig():
    secret = "test-secret-key"
    payload = '{"response_id": "abc123"}'
    assert hmac_verify(secret, payload, "wrong-signature") is False


def test_hmac_verify_wrong_secret():
    payload = '{"response_id": "abc123"}'
    sig = hmac_sign("secret-a", payload)
    assert hmac_verify("secret-b", payload, sig) is False


async def test_unknown_api_key_returns_401_not_500(monkeypatch):
    """An unknown key prefix must yield a clean 401, not a 500 from .single()
    raising on 0 rows. Regression test for the auth maybe_single() fix."""
    import app.core.auth as auth_mod
    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials

    class _FakeRedis:
        def get(self, _k):
            return None

    class _FakeQuery:
        def select(self, *a):
            return self

        def eq(self, *a):
            return self

        def maybe_single(self):
            return self

        def execute(self):
            class _R:
                data = None
            return _R()

    class _FakeDB:
        def table(self, *a):
            return _FakeQuery()

    monkeypatch.setattr(auth_mod, "get_redis", lambda: _FakeRedis())
    monkeypatch.setattr(auth_mod, "get_db", lambda: _FakeDB())

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="sk_live_doesnotexist")
    with pytest.raises(HTTPException) as exc_info:
        await auth_mod.verify_api_key_dep(creds)
    assert exc_info.value.status_code == 401
