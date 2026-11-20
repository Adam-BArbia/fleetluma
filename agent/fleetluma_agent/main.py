"""Run: python -m fleetluma_agent.main (from agent directory)."""
import json
import logging
import os
from ipaddress import ip_address, ip_network
import sys
import time
from pathlib import Path
from urllib import error, request
from urllib.parse import urlsplit

from .collector import build_report

LOG = logging.getLogger("fleetluma.agent")


def load_config(env=None):
    env = env or os.environ
    url = env.get("FLEETLUMA_COORDINATOR_URL", "").rstrip("/")
    token = env.get("FLEETLUMA_AGENT_TOKEN", "")
    if not url or len(token) < 16 or token.startswith("REPLACE_"):
        raise ValueError("Set FLEETLUMA_COORDINATOR_URL and a real unique agent token")
    parts = urlsplit(url)
    if (parts.scheme not in {"http", "https"} or not parts.netloc
            or parts.username or parts.password or parts.query or parts.fragment
            or parts.path not in ("", "/")):
        raise ValueError("Coordinator must have an HTTP(S) origin without credentials or paths")
    if parts.scheme == "http":
        if env.get("FLEETLUMA_MODE") == "cloud" or env.get("FLEETLUMA_REQUIRE_HTTPS") == "true":
            raise ValueError("Cloud agent reporting requires HTTPS")
        if parts.hostname not in {"127.0.0.1", "localhost"}:
            if env.get("FLEETLUMA_ALLOW_INSECURE_LAN") != "true":
                raise ValueError("Non-loopback HTTP is disabled by default; use HTTPS")
            # Even the explicit lab exception must target a numeric RFC1918 IP.
            # No public or DNS-rebound endpoint may receive plaintext tokens.
            try:
                addr = ip_address(parts.hostname)
            except ValueError:
                raise ValueError("HTTP lab coordinator must use a private IP address") from None
            private_lan = any(addr in ip_network(cidr) for cidr in
                ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
            if not private_lan:
                raise ValueError("HTTP lab coordinator must use a private IP address")
            LOG.warning("Unsafe HTTP LAN mode explicitly enabled; agent bearer tokens are unencrypted")
    disk = env.get("FLEETLUMA_DISK_PATH", os.path.abspath(os.sep))
    if not Path(disk).exists():
        raise ValueError("FLEETLUMA_DISK_PATH does not exist")
    interval = int(env.get("FLEETLUMA_INTERVAL_SECONDS", "10"))
    if interval < 2 or interval > 3600:
        raise ValueError("Reporting interval must be 2..3600 seconds")
    return url, token, disk, interval


class NoRedirect(request.HTTPRedirectHandler):
    """Never forward an agent bearer token to an HTTP redirect destination."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def send_report(url, token, report, timeout=5):
    data = json.dumps(report).encode("utf-8")
    req = request.Request(url + "/api/v1/agent/reports", data=data, method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + token})
    # urllib normally follows 30x redirects; that would expose bearer tokens
    # to the destination host, including a different domain or HTTP scheme.
    # Ignore inherited HTTP(S)_PROXY settings: agent tokens only go to the
    # coordinator configured by its administrator, using direct TLS.
    opener = request.build_opener(request.ProxyHandler({}), NoRedirect())
    with opener.open(req, timeout=timeout) as response:
        if response.status != 202:
            raise RuntimeError("Coordinator rejected report: HTTP " + str(response.status))
        return json.load(response)


def run():
    url, token, disk, interval = load_config()
    LOG.info("FleetLuma agent started; report interval=%ss", interval)
    attempt = 0
    next_process_collection = 0.0
    while True:
        now = time.monotonic()
        try:
            # Send a bounded process snapshot every ~30 seconds.
            report = build_report(disk, include_processes=(now >= next_process_collection))
            if "processes" in report:
                next_process_collection = now + 30.0
            send_report(url, token, report)
            attempt = 0
            LOG.info("Agent report accepted")
            time.sleep(interval)
        except (error.URLError, OSError, ValueError, RuntimeError) as exc:
            # Never log credentials or payload content.
            attempt += 1
            LOG.warning("Report failed (%s); retrying", type(exc).__name__)
            time.sleep(min(60, max(2, 2 ** min(attempt, 5))))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        run()
    except (ValueError, KeyboardInterrupt) as exc:
        if isinstance(exc, ValueError):
            LOG.error("Invalid configuration")
            sys.exit(2)
