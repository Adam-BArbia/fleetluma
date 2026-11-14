"""FL-18: real RSA JWT signature and authorization boundary tests."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
import pytest

from fleetluma_backend import operator_auth


class SigningKey:
    def __init__(self, key):
        self.key = key


def test_valid_supabase_jwt_and_denial_cases(monkeypatch):
    project_url = "https://mulsyhgdigonccziywet.supabase.co"
    operator_id, outsider_id = str(uuid4()), str(uuid4())
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = key.public_key()
    monkeypatch.setenv("FLEETLUMA_MODE", "cloud")
    monkeypatch.setenv("FLEETLUMA_SUPABASE_URL", project_url)
    monkeypatch.setenv("FLEETLUMA_OPERATOR_IDS", operator_id)

    class Client:
        def get_signing_key_from_jwt(self, token):
            return SigningKey(public_key)
    monkeypatch.setattr(operator_auth, "jwks_client", lambda _: Client())

    def signed(subject=operator_id, role="authenticated", issuer=None,
               expires=None, key_to_sign=None):
        now = datetime.now(timezone.utc)
        claims = {
            "sub": subject, "role": role,
            "iss": issuer or project_url + "/auth/v1",
            "aud": "authenticated",
            "iat": int(now.timestamp()),
            "exp": int((expires or (now + timedelta(minutes=15))).timestamp()),
        }
        return jwt.encode(claims, key_to_sign or key, algorithm="RS256")

    assert operator_auth.require_operator("Bearer " + signed()) == operator_id
    cases = [
        (signed(subject=outsider_id), 403),
        (signed(role="anon"), 403),
        (signed(issuer="https://attacker.supabase.co/auth/v1"), 401),
        (signed(expires=datetime.now(timezone.utc) - timedelta(minutes=3)), 401),
        (signed(key_to_sign=rsa.generate_private_key(public_exponent=65537, key_size=2048)), 401),
    ]
    for token, code in cases:
        with pytest.raises(HTTPException) as err:
            operator_auth.require_operator("Bearer " + token)
        assert err.value.status_code == code
