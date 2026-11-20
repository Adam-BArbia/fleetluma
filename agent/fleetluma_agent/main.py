"""Run: python -m fleetluma_agent.main (from agent directory)."""
import json
import logging
import os
import sys
import time
from pathlib import Path
from urllib import error, request
from urllib.parse import urlsplit

from .collector import build_report

LOG = logging.getLogger("fleetluma.agent")

class _RejectRedirects(request.HTTPRedirectHandler):
    """Never replay agent bearer tokens to a redirect target."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _validate_coordinator_url(url, allow_insecure_lan=False):
    parts = urlsplit(url)
    if (parts.scheme not in {"http", "https"} or not parts.hostname
            or parts.username is not None or parts.password is not None
            or parts.path not in ("", "/") or parts.query or parts.fragment
            or (parts.port is not None and not (1 <= parts.port <= 65535))):
        raise ValueError("Coordinator must be HTTP(S) origin without credentials/path")
    if parts.scheme != "https":
        if parts.hostname not in {"localhost", "127.0.0.1", "::1"} and not allow_insecure_lan:
            raise ValueError("Remote coordinator requires HTTPS; insecure LAN is opt-in")
    return parts



def load_config(env=None):
    env = env or os.environ
    url = env.get("FLEETLUMA_COORDINATOR_URL", "").rstrip("/")
    token = env.get("FLEETLUMA_AGENT_TOKEN", "")
    if not url or not token or token.startswith("REPLACE_"):
        raise ValueError("Set FLEETLUMA_COORDINATOR_URL and a real unique agent token")
    allow_insecure_lan = env.get("FLEETLUMA_ALLOW_INSECURE_LAN", "").lower() == "true"
    parts = _validate_coordinator_url(url, allow_insecure_lan)
    if env.get("FLEETLUMA_AGENT_CLOUD_MODE", "").lower() == "true" and parts.scheme != "https":
        raise ValueError("Cloud agents require HTTPS even on localhost")
    if parts.scheme == "http" and allow_insecure_lan:
        LOG.warning("Unencrypted LAN mode is for trusted temporary labs only")
    disk = env.get("FLEETLUMA_DISK_PATH", os.path.abspath(os.sep))
    if not Path(disk).exists():
        raise ValueError("FLEETLUMA_DISK_PATH does not exist")
    interval = int(env.get("FLEETLUMA_INTERVAL_SECONDS", "10"))
    if interval < 2 or interval > 3600:
        raise ValueError("Reporting interval must be 2..3600 seconds")
    return url, token, disk, interval


def send_report(url, token, report, timeout=5, allow_insecure_lan=False):
    _validate_coordinator_url(url, allow_insecure_lan)
    data = json.dumps(report).encode("utf-8")
    req = request.Request(url + "/api/v1/agent/reports", data=data, method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + token})
    with request.build_opener(_RejectRedirects()).open(req, timeout=timeout) as response:
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
            send_report(url, token, report,
                allow_insecure_lan=os.environ.get('FLEETLUMA_ALLOW_INSECURE_LAN', '').lower() == 'true')
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
