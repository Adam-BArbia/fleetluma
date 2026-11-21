"""Protect operator read routes in cloud mode. Agent tokens remain independent."""
import os
from functools import lru_cache
from urllib.parse import urlparse
from uuid import UUID

import jwt
from jwt import PyJWKClient
from fastapi import Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware


def cloud_mode():
    return os.environ.get("FLEETLUMA_MODE", "local") == "cloud"


def issuer():
    url = os.environ.get("FLEETLUMA_SUPABASE_URL", "").rstrip("/")
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.username or parsed.password
            or parsed.port or parsed.path or parsed.query or parsed.fragment
            or not (parsed.hostname or "").endswith(".supabase.co")):
        raise RuntimeError("Cloud auth requires verified HTTPS Supabase project origin")
    return url + "/auth/v1"


@lru_cache(maxsize=8)
def jwks_client(issuer_url):
    return PyJWKClient(issuer_url + "/.well-known/jwks.json", cache_keys=True)


def allowed_operators():
    raw = os.environ.get("FLEETLUMA_OPERATOR_IDS", "")
    if not raw.strip():
        raise RuntimeError("Cloud mode must explicitly configure operator UUID allowlist")
    return {str(UUID(x.strip())) for x in raw.split(",") if x.strip()}


def require_operator(authorization: str | None = Header(default=None)):
    """Local prototype accepts LAN reads; cloud always enforces Supabase JWT."""
    if not cloud_mode():
        return None
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Operator authentication required")
    token = authorization[len("Bearer "):].strip()
    try:
        identity_provider = issuer()
        signing_key = jwks_client(identity_provider).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token, signing_key.key, algorithms=["RS256", "ES256"],
            issuer=identity_provider, audience="authenticated",
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            leeway=15,
        )
        subject = str(UUID(claims["sub"]))
        if claims.get("role") != "authenticated" or subject not in allowed_operators():
            raise HTTPException(403, "Operator access denied")
        return subject
    except HTTPException:
        raise
    except (jwt.PyJWTError, ValueError, OSError, RuntimeError):
        raise HTTPException(401, "Invalid or expired operator token") from None


def configure_cors(app):
    if cloud_mode():
        origins = [x.strip() for x in os.environ.get("FLEETLUMA_WEB_ORIGINS", "").split(",") if x.strip()]
        # The API preview can precede Flutter Web. With no origins configured,
        # browser cross-origin access is disabled until an exact Web URL exists.
        if not origins:
            return
        for origin in origins:
            parsed = urlparse(origin)
            if (parsed.scheme != "https" or not parsed.hostname or
                    parsed.username is not None or parsed.password is not None or
                    parsed.port is not None or parsed.path or parsed.query or parsed.fragment or
                    "*" in origin or origin != parsed.geturl()):
                raise RuntimeError("Cloud CORS only accepts explicit HTTPS origins")
        app.add_middleware(CORSMiddleware, allow_origins=origins,
                           allow_credentials=False, allow_methods=["GET","POST","PATCH","OPTIONS"],
                           allow_headers=["Authorization","Content-Type"])
