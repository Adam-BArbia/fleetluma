"""FL-32 pairing core security and input contract tests."""
from datetime import datetime, timedelta, timezone
import hashlib
import re

import pytest

from fleetluma_backend.pairing_core import (
    ALPHABET, CODE_TTL, POLL_INTERVAL_SECONDS,
    code_digest, hash_secret, new_pairing_ticket, new_reporting_token,
    normalize_code, validate_agent_metadata,
)

PEPPER = "ci-only-pairing-pepper-keep-secret-never-in-source"


def test_ticket_generates_distinct_secrets_and_ten_minute_expiry():
    now = datetime(2026, 11, 21, tzinfo=timezone.utc)
    first = new_pairing_ticket(PEPPER, now=now)
    second = new_pairing_ticket(PEPPER, now=now)
    assert len(ALPHABET) == 32
    assert len(first.user_code) == 9
    assert first.expires_at == now + CODE_TTL
    assert POLL_INTERVAL_SECONDS == 5
    assert first.device_code != second.device_code
    assert first.user_code != second.user_code
    assert first.user_code_hash == code_digest(first.user_code, PEPPER)
    assert first.device_code_hash == hash_secret(first.device_code)
    assert first.device_code_hash != first.user_code_hash
    assert first.device_code not in (first.user_code, first.user_code_hash)


def test_normalize_and_reject_ambiguous_codes():
    assert normalize_code("abcd-7294") == "ABCD-7294"
    assert normalize_code("ABCD7294") == "ABCD-7294"
    for invalid in ("ABCD-I234", "ABCD-O234", "ABCD-123", "abc<script", ""):
        with pytest.raises(ValueError):
            normalize_code(invalid)


def test_weak_pepper_is_forbidden_and_hash_depends_on_pepper():
    with pytest.raises(ValueError):
        code_digest("ABCD-7294", "weak")
    assert code_digest("ABCD-7294", PEPPER) != code_digest(
        "ABCD-7294", "another-ci-only-secret-pepper-32characters"
    )


def test_reporting_token_uses_independent_entropy():
    a = new_reporting_token()
    b = new_reporting_token()
    assert a != b
    assert a != hash_secret(a)
    assert len(a) >= 40


def test_agent_metadata_validation():
    digest = hashlib.sha256(b"random-credential-example").hexdigest()
    validate_agent_metadata("TUFFEST", "windows", "0.1.0", digest,
                            ["cpu", "ram", "disk", "processes"])
    for bad in ("", "../evil", "bad space", "\nlog-injection"):
        with pytest.raises(ValueError):
            validate_agent_metadata(bad, "windows", "0.1.0", digest, [])
    for bad_digest in ("0" * 63, "G" * 64, "token", ""):
        with pytest.raises(ValueError):
            validate_agent_metadata("machine", "linux", "0.1.0", bad_digest, [])
    with pytest.raises(ValueError):
        validate_agent_metadata("machine", "linux", "0.1.0", digest, ["bad command;"])
