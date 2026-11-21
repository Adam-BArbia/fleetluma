"""FL-33: device-initiated pairing HTTP client (transport only).

This module intentionally does NOT persist credentials, install a service,
or present a GUI. Platform credential storage belongs to service packaging.
Never log, print, or put any of these secrets in command-line arguments.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from ipaddress import ip_address
from urllib import error, request
from urllib.parse import urlsplit


@dataclass(frozen=True)
class PairingStarted:
    user_code: str
    device_code: str
    verification_uri: str
    interval: int
    expires_in: int


@dataclass(frozen=True)
class PairingAccepted:
    host_id: str
    workspace_id: str


class PairingRejected(Exception):
    def __init__(self, status: int):
        self.status = status
        super().__init__("Enrollment rejected (HTTP %s)" % status)


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def verified_https_origin(origin: str) -> str:
    if not isinstance(origin, str):
        raise ValueError("Coordinator origin must be HTTPS")
    parsed = urlsplit(origin)
    if (parsed.scheme != "https" or not parsed.hostname or
            parsed.username or parsed.password or parsed.query or
            parsed.fragment or parsed.path not in ("", "/")):
        raise ValueError("Coordinator origin must be HTTPS without paths or credentials")
    if parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Pairing requires externally trusted HTTPS coordinator")
    return origin.rstrip("/")


class PairingHttpClient:
    def __init__(self, origin: str, opener=None):
        self.origin = verified_https_origin(origin)
        self.opener = opener or request.build_opener(request.ProxyHandler({}), NoRedirect())

    def _post(self, path: str, document: dict) -> dict:
        body = json.dumps(document, separators=(",", ":")).encode("utf-8")
        if len(body) > 8192:
            raise ValueError("Pairing request is too large")
        req = request.Request(
            self.origin + path, data=body, method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json"})
        try:
            with self.opener.open(req, timeout=8) as response:
                if response.status not in (200, 201):
                    raise PairingRejected(response.status)
                raw = response.read(8193)
                if len(raw) > 8192:
                    raise ValueError("Enrollment response too large")
                return json.loads(raw.decode("utf-8"))
        except error.HTTPError as exc:
            # Only status is safe to expose; never echo headers/body/tokens.
            raise PairingRejected(exc.code) from None

    def start(self, *, hostname: str, platform: str, version: str,
              report_token: str, capabilities: list[str]) -> PairingStarted:
        if not isinstance(report_token, str) or len(report_token) < 40:
            raise ValueError("Provide independently generated strong reporting secret")
        result = self._post("/api/v1/agent/pairings", {
            "hostname": hostname, "platform": platform, "agent_version": version,
            "report_token_sha256": hashlib.sha256(report_token.encode()).hexdigest(),
            "capabilities": capabilities})
        if (result.get("expires_in") != 600 or result.get("interval", 0) < 5
                or not isinstance(result.get("device_code"), str)
                or len(result["device_code"]) < 32
                or not isinstance(result.get("user_code"), str)
                or len(result["user_code"]) != 9):
            raise ValueError("Invalid enrollment response")
        uri = result.get("verification_uri", "")
        if not isinstance(uri, str) or not uri.startswith("https://"):
            raise ValueError("Invalid verification URI")
        return PairingStarted(
            user_code=result["user_code"], device_code=result["device_code"],
            verification_uri=uri, interval=result["interval"],
            expires_in=result["expires_in"])

    def poll(self, ticket: PairingStarted) -> PairingAccepted | None:
        answer = self._post("/api/v1/agent/pairings/token", {
            "device_code": ticket.device_code})
        if answer.get("status") == "pending":
            return None
        if (answer.get("status") != "paired" or
                not answer.get("host_id") or not answer.get("workspace_id")):
            raise ValueError("Unexpected enrollment result")
        return PairingAccepted(answer["host_id"], answer["workspace_id"])

    def cancel(self, ticket: PairingStarted):
        # 204 has no JSON body; explicitly avoid decoding a successful empty response.
        request_body = json.dumps({"device_code": ticket.device_code}).encode("utf-8")
        req = request.Request(self.origin + "/api/v1/agent/pairings/cancel",
                              data=request_body, method="POST",
                              headers={"Content-Type": "application/json"})
        try:
            with self.opener.open(req, timeout=8) as response:
                if response.status != 204:
                    raise PairingRejected(response.status)
        except error.HTTPError as exc:
            raise PairingRejected(exc.code) from None


def generate_reporting_secret() -> str:
    """Cryptographically random 256-bit agent-only secret."""
    return secrets.token_urlsafe(32)
