"""FL-32 pairing primitives. No database/network calls and no tokens in logs."""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_TTL = timedelta(minutes=10)
POLL_INTERVAL_SECONDS = 5
HOST_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$")
TOKEN_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
VERSION_RE = re.compile(r"^[0-9A-Za-z._+-]{1,64}$")


@dataclass(frozen=True)
class PairingTicket:
    user_code: str
    device_code: str
    user_code_hash: str
    device_code_hash: str
    expires_at: datetime


def hash_secret(secret: str) -> str:
    """Safe only when secret has at least 128 bits of randomness."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def code_digest(code: str, pepper: str) -> str:
    """User code is low entropy: use keyed HMAC to impede offline guessing."""
    if len(pepper) < 32:
        raise ValueError("Pairing HMAC key must be at least 32 characters")
    normalized = normalize_code(code)
    return hmac.new(pepper.encode("utf-8"), normalized.encode("ascii"), hashlib.sha256).hexdigest()


def normalize_code(code: str) -> str:
    if not isinstance(code, str):
        raise ValueError("Invalid pairing code")
    clean = code.replace("-", "").strip().upper()
    if len(clean) != 8 or any(ch not in ALPHABET for ch in clean):
        raise ValueError("Invalid pairing code")
    return clean[:4] + "-" + clean[4:]


def new_reporting_token() -> str:
    return secrets.token_urlsafe(32)  # 256 random bits


def new_pairing_ticket(pepper: str, now: datetime | None = None) -> PairingTicket:
    code = "".join(secrets.choice(ALPHABET) for _ in range(8))
    visible = code[:4] + "-" + code[4:]
    private = secrets.token_urlsafe(32)  # independent 256 random bits
    now = now or datetime.now(timezone.utc)
    return PairingTicket(
        user_code=visible, device_code=private,
        user_code_hash=code_digest(visible, pepper),
        device_code_hash=hash_secret(private),
        expires_at=now + CODE_TTL,
    )


def validate_agent_metadata(hostname: str, platform: str, version: str,
                            digest: str, capabilities: list[str]) -> None:
    if not isinstance(hostname, str) or not HOST_RE.fullmatch(hostname):
        raise ValueError("Invalid agent hostname")
    if platform not in {"windows", "linux"}:
        raise ValueError("Invalid agent platform")
    if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
        raise ValueError("Invalid agent version")
    if not isinstance(digest, str) or not TOKEN_DIGEST_RE.fullmatch(digest):
        raise ValueError("Invalid reporting token digest")
    if not isinstance(capabilities, list) or len(capabilities) > 20:
        raise ValueError("Invalid capabilities")
    if any(not isinstance(x, str) or len(x) > 40 or not re.fullmatch(r"[a-z_]{1,40}", x)
           for x in capabilities):
        raise ValueError("Invalid capabilities")
