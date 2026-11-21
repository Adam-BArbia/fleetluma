"""FL-36: private pairing state machine and monitored-service runtime.

Only callable by the trusted service process. The forthcoming desktop setup
companion must communicate over OS-ACL-protected local IPC. Until that IPC is
implemented, no public/local HTTP endpoint may invoke these operations.
"""
from __future__ import annotations

import logging
import platform
import socket
import threading
import time
from dataclasses import dataclass
from urllib import error

from .collector import build_report
from .main import send_report
from .pairing_client import (
    PairingHttpClient, PairingRejected, PairingStarted,
    generate_reporting_secret,
)
from .secure_state import (
    AgentIdentity, CredentialMissing, ProtectedCredentialStore,
)

LOG = logging.getLogger("fleetluma.agent.service")


@dataclass(frozen=True)
class PublicPairingStatus:
    status: str
    user_code: str | None = None
    verification_uri: str | None = None
    expires_in: int | None = None
    host_id: str | None = None
    # No device_code, report_token or private URL parameters.


class NeedsRepair(Exception):
    """Agent credentials are no longer authorized; deliberate re-pairing required."""


class EnrollmentController:
    def __init__(self, store: ProtectedCredentialStore, client: PairingHttpClient,
                 clock=time.monotonic):
        self.store = store
        self.client = client
        self.clock = clock
        self._lock = threading.RLock()
        self._ticket: PairingStarted | None = None
        self._report_token: str | None = None
        self._started_at: float | None = None
        self._next_poll_at: float | None = None

    def _paired(self) -> AgentIdentity | None:
        try:
            return self.store.load()
        except CredentialMissing:
            return None

    def status(self) -> PublicPairingStatus:
        with self._lock:
            paired = self._paired()
            if paired is not None:
                return PublicPairingStatus(status="paired", host_id=paired.host_id)
            if self._ticket is None:
                return PublicPairingStatus(status="not_paired")
            elapsed = self.clock() - self._started_at
            remaining = max(0, self._ticket.expires_in - int(elapsed))
            if remaining == 0:
                return PublicPairingStatus(status="expired")
            return PublicPairingStatus(
                status="waiting", user_code=self._ticket.user_code,
                verification_uri=self._ticket.verification_uri,
                expires_in=remaining)

    def begin(self, version: str = "0.1.0") -> PublicPairingStatus:
        with self._lock:
            if self._paired() is not None:
                raise ValueError("Device is already paired; explicit revocation required")
            if self._ticket is not None and self.status().status == "waiting":
                return self.status()
            secret = generate_reporting_secret()
            system = platform.system().lower()
            if system not in ("windows", "linux"):
                raise ValueError("FleetLuma agent supports Windows and Linux")
            hostname = socket.gethostname()
            # Truncate rather than forwarding unbounded hostname into requests.
            ticket = self.client.start(
                hostname=hostname[:64], platform=system,
                version=version, report_token=secret,
                capabilities=["cpu", "ram", "disk", "processes"])
            self._ticket = ticket
            self._report_token = secret
            self._started_at = self.clock()
            self._next_poll_at = self._started_at + ticket.interval
            return self.status()

    def poll_once(self) -> PublicPairingStatus:
        with self._lock:
            if self._paired() is not None:
                return self.status()
            if self._ticket is None or self._report_token is None:
                raise ValueError("No pending pairing")
            if self.status().status == "expired":
                self._clear_pending()
                return PublicPairingStatus(status="expired")
            if self.clock() < self._next_poll_at:
                return self.status()
            # Pacing is bounded locally as well as by server-side rate limiting.
            self._next_poll_at = self.clock() + max(5, self._ticket.interval)
            try:
                accepted = self.client.poll(self._ticket)
            except PairingRejected as exc:
                if exc.status in (403, 410):
                    self._clear_pending()
                    return PublicPairingStatus(
                        status="denied" if exc.status == 403 else "expired")
                if exc.status == 429:
                    self._next_poll_at = self.clock() + max(10, self._ticket.interval)
                    return self.status()
                raise
            if accepted is None:
                return self.status()
            identity = AgentIdentity(
                host_id=accepted.host_id,
                workspace_id=accepted.workspace_id,
                report_token=self._report_token,
                api_origin=self.client.origin)
            self.store.store(identity)
            self._clear_pending()
            return PublicPairingStatus(status="paired", host_id=identity.host_id)

    def cancel(self) -> None:
        with self._lock:
            if self._ticket is not None:
                try:
                    self.client.cancel(self._ticket)
                finally:
                    self._clear_pending()

    def _clear_pending(self):
        self._ticket = None
        self._report_token = None
        self._started_at = None
        self._next_poll_at = None


def run_paired_service(
    store: ProtectedCredentialStore, disk_path: str, interval: int = 10,
    stop_event: threading.Event | None = None, report_sender=send_report,
    collector=build_report, pause=time.sleep, clock=time.monotonic,
) -> None:
    """Run only after an approved identity is already protected on disk.

    Existing TUFFEST legacy env-token run path remains separate. HTTP 401
    immediately stops reporting rather than retrying revoked credentials.
    """
    if not 2 <= interval <= 3600:
        raise ValueError("Invalid reporting interval")
    identity = store.load()
    stop_event = stop_event or threading.Event()
    next_process_sample = 0.0
    failed = 0
    while not stop_event.is_set():
        now = clock()
        try:
            report = collector(disk_path, include_processes=now >= next_process_sample)
            if "processes" in report:
                next_process_sample = now + 30
            report_sender(identity.api_origin, identity.report_token, report)
            failed = 0
            LOG.info("Agent report accepted")
            if stop_event.wait(interval):
                break
        except error.HTTPError as exc:
            if exc.code in (401, 403):
                raise NeedsRepair("Agent access revoked; authorize a new pairing") from None
            failed += 1
            LOG.warning("Report request failed; applying backoff")
            if stop_event.wait(min(60, max(2, 2 ** min(failed, 5)))):
                break
        except (OSError, ValueError, RuntimeError, error.URLError):
            failed += 1
            LOG.warning("Agent network or collection error; applying backoff")
            if stop_event.wait(min(60, max(2, 2 ** min(failed, 5)))):
                break
