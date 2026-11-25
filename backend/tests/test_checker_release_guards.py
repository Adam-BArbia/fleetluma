"""Static CI gate for a deliberately inactive, restricted cloud checker.

These checks protect the relationship between Supabase gateway configuration
and the server-side named key authenticator. They do not replace runtime
authentication, DNS/egress verification or the final operator acceptance.
"""
from pathlib import Path
import re
import tomllib

PROJECT = Path(__file__).resolve().parents[2]
CHECKER = PROJECT / "supabase" / "functions" / "fleetluma-checker" / "index.ts"
CONFIG = PROJECT / "supabase" / "config.toml"
CRON = PROJECT / "backend" / "sql" / "FL-29_checker_cron_REVIEW_ONLY.sql"


def test_checker_gateway_is_never_open_without_named_key_auth():
    config = tomllib.loads(CONFIG.read_text(encoding="utf-8"))
    checker = config["functions"]["fleetluma-checker"]
    source = CHECKER.read_text(encoding="utf-8")
    assert checker["verify_jwt"] is False
    assert 'withSupabase({ auth: "secret:fleetluma-checker" }' in source
    assert 'auth: "none"' not in source
    assert 'auth: "publishable"' not in source


def test_probe_cannot_activate_without_explicit_approval_flags():
    source = CHECKER.read_text(encoding="utf-8")
    assert 'FLEETLUMA_PUBLIC_PROBES_ENABLED' in source
    assert 'FLEETLUMA_CHECK_ALLOWED_HOSTS' in source
    assert '!== "true"' in source
    assert "enabled=true" in source
    assert "verifyPublicDns(target)" in source
    assert "allowedTarget(service.url, allowed)" in source
    assert "probePinned(service.url, allowed, verifiedIp)" in source
    assert "const verifiedIp = await verifyPublicDns(target)" in source
    assert "await probe(service.url" not in source
    checker = (PROJECT / "supabase" / "functions" /
               "fleetluma-checker" / "checker.ts").read_text(encoding="utf-8")
    assert "rejectUnauthorized: true" in checker
    assert "serverName:" not in checker
    assert "servername: url.hostname" in checker
    assert "callback(null, verifiedIp, 4)" in checker
    assert "socket.remoteAddress !== verifiedIp" in checker



def test_cron_is_a_review_template_and_not_an_active_sql_migration():
    source = CRON.read_text(encoding="utf-8")
    assert "fleetluma_checker_api_key" in source
    assert "'apikey'" in source
    assert "vault.decrypted_secrets" in source
    assert "FLEETLUMA_PUBLIC_PROBES_ENABLED" in source
    # The Cron activation command must be comment-prefixed on every line.
    assert not re.search(r"(?m)^\s*(?!--)SELECT\s+cron\.schedule\s*\(", source)
    assert re.search(r"(?m)^--\s+SELECT\s+cron\.schedule\s*\(", source)
    assert not re.search(r"(?m)^\s*(?!--)SELECT\s+cron\.unschedule\s*\(", source)
