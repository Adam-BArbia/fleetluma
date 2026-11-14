"""FL-20 preview smoke checks. Never receives or prints secrets.

Usage:
  python scripts/verify_cloud_preview.py https://fleetluma-api-preview.vercel.app

This script intentionally validates only public, non-credentialled boundaries:
a working /health and unauthorized GET /api/v1/hosts. The authenticated
browser/agent/DB integration must be separately demonstrated before FL-20 Done.
"""
import json
import sys
from urllib import error, request
from urllib.parse import urlsplit


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_preview_url(value):
    parts = urlsplit(value)
    hostname = (parts.hostname or "").lower()
    if (
        parts.scheme != "https"
        or not hostname.endswith(".vercel.app")
        or parts.username is not None
        or parts.password is not None
        or parts.port is not None
        or parts.path not in ("", "/")
        or parts.query
        or parts.fragment
    ):
        raise ValueError("Expected an origin-only HTTPS .vercel.app preview URL")
    return value.rstrip("/")


def validate_response(path, code, payload):
    if path == "/health":
        try:
            data = json.loads(payload)
        except (ValueError, TypeError) as exc:
            raise AssertionError("Health did not return JSON") from exc
        if code != 200 or data.get("status") != "ready" or data.get("mode") != "cloud":
            raise AssertionError("Cloud health readiness failed")
    elif path == "/api/v1/hosts":
        if code != 401:
            raise AssertionError(
                f"Unauthenticated fleet GET must return 401, got {code}"
            )
    else:
        raise ValueError("Unsupported verification path")


def run(origin):
    origin = validate_preview_url(origin)
    opener = request.build_opener(
        request.ProxyHandler({}),
        NoRedirect(),
    )
    for path in ("/health", "/api/v1/hosts"):
        req = request.Request(origin + path, headers={"Accept": "application/json"})
        try:
            with opener.open(req, timeout=10) as response:
                code = response.status
                payload = response.read(100_000)
        except error.HTTPError as exc:
            code = exc.code
            payload = exc.read(100_000)
            exc.close()
        validate_response(path, code, payload)
        print(f"PASS {path}: HTTP {code}")
    print("PASS public preview boundary. Authenticated smoke tests still required.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/verify_cloud_preview.py HTTPS_VERCEL_API_ORIGIN")
    try:
        run(sys.argv[1])
    except (AssertionError, ValueError, OSError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
