"""FL-18: cloud authentication must fail closed; local mode stays compatible."""
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fleetluma_backend import operator_auth as auth


def test_local_mode_preserves_original_lan_behavior(monkeypatch):
    monkeypatch.delenv("FLEETLUMA_MODE", raising=False)
    assert auth.require_operator(None) is None


def test_cloud_rejects_missing_auth_header(monkeypatch):
    monkeypatch.setenv("FLEETLUMA_MODE", "cloud")
    with pytest.raises(HTTPException) as exc:
        auth.require_operator(None)
    assert exc.value.status_code == 401


def test_rejects_untrusted_supabase_issuer(monkeypatch):
    monkeypatch.setenv("FLEETLUMA_SUPABASE_URL", "http://attacker.invalid")
    with pytest.raises(RuntimeError):
        auth.issuer()


def test_requires_explicit_operator_allowlist(monkeypatch):
    monkeypatch.delenv("FLEETLUMA_OPERATOR_IDS", raising=False)
    with pytest.raises(RuntimeError):
        auth.allowed_operators()


def test_rejects_jwt_without_valid_signature(monkeypatch):
    monkeypatch.setenv("FLEETLUMA_MODE", "cloud")
    monkeypatch.setenv("FLEETLUMA_SUPABASE_URL", "https://demo.supabase.co")
    with pytest.raises(HTTPException) as exc:
        auth.require_operator("Bearer invalid.jwt.signature")
    assert exc.value.status_code == 401


def test_valid_signed_claims_still_need_allowlisted_operator(monkeypatch):
    monkeypatch.setenv("FLEETLUMA_MODE", "cloud")
    monkeypatch.setenv("FLEETLUMA_SUPABASE_URL", "https://demo.supabase.co")
    monkeypatch.setenv("FLEETLUMA_OPERATOR_IDS", str(uuid4()))
    subject = str(uuid4())
    class Key:
        key = "fake-public-key"
    class Client:
        def get_signing_key_from_jwt(self, token):
            return Key()
    monkeypatch.setattr(auth, "jwks_client", lambda _: Client())
    monkeypatch.setattr(auth.jwt, "decode", lambda *args, **kwargs: {
        "sub": subject, "role": "authenticated"
    })
    with pytest.raises(HTTPException) as exc:
        auth.require_operator("Bearer fixture-jwt")
    assert exc.value.status_code == 403


def test_cloud_cors_rejects_wildcard(monkeypatch):
    from fastapi import FastAPI
    monkeypatch.setenv("FLEETLUMA_MODE", "cloud")
    monkeypatch.setenv("FLEETLUMA_WEB_ORIGINS", "*")
    with pytest.raises(RuntimeError):
        auth.configure_cors(FastAPI())
