"""FL-37 service-friendly startup: loads only service-owned saved credentials.

Packagers must install this under a restricted Windows service identity or
Linux systemd User=fleetluma. No token in arguments, env, or stdout. The
separate setup companion + authenticated IPC are still required for pairing.
"""
from __future__ import annotations

import hashlib
import logging
import os
import signal
import sys
import threading
from pathlib import Path

from .secure_state import CredentialMissing, ProtectedCredentialStore
from .service_runtime import NeedsRepair, run_paired_service

LOG = logging.getLogger("fleetluma.agent.supervisor")


def default_identity_path(platform=sys.platform) -> Path:
    """Installed locations only. Parent permissions/ACL are installer-owned."""
    if platform == "win32":
        program_data = os.environ.get("PROGRAMDATA")
        if not program_data:
            raise RuntimeError("Windows service requires ProgramData")
        return Path(program_data) / "FleetLuma" / "private" / "identity.bin"
    if platform.startswith("linux"):
        return Path("/var/lib/fleetluma/private/identity.bin")
    raise RuntimeError("Only Windows and Linux agents are supported")


def run_supervisor(store: ProtectedCredentialStore, *,
                   disk_path: str, stop_event: threading.Event,
                   poll_interval: float = 5.0, reporter=run_paired_service) -> None:
    """Start when credentials appear, survive reboots, stop on revocation.

    A revoked credential is never retried: resume requires a **new** different
    locally stored reporting token after explicit operator authorization.
    """
    if poll_interval < 1:
        raise ValueError("Invalid wait interval")
    warned_missing = False
    blocked_digest: str | None = None
    while not stop_event.is_set():
        try:
            identity = store.load()
        except CredentialMissing:
            if not warned_missing:
                LOG.info("Agent not paired; waiting for approved enrollment")
                warned_missing = True
            stop_event.wait(poll_interval)
            continue
        except (OSError, ValueError, PermissionError):
            LOG.error("Protected identity unavailable; requires local repair")
            stop_event.wait(poll_interval)
            continue
        warned_missing = False
        fingerprint = hashlib.sha256(identity.report_token.encode()).hexdigest()
        if blocked_digest == fingerprint:
            stop_event.wait(poll_interval)
            continue
        try:
            reporter(store, disk_path=disk_path, stop_event=stop_event)
        except NeedsRepair:
            blocked_digest = fingerprint
            LOG.warning("Agent authorization revoked; explicit re-pair required")
        except (OSError, RuntimeError, ValueError):
            # Unexpected failure must not disclose tokens or URLs.
            LOG.error("Agent monitoring stopped unexpectedly; retrying")
        if not stop_event.is_set():
            stop_event.wait(poll_interval)


def start_linux_control(store, stop_event, origin, runtime_dir=Path("/run/fleetluma")):
    """Only started for Linux under the dedicated systemd service account."""
    if not sys.platform.startswith("linux"):
        raise RuntimeError("Linux control requires Linux")
    from .pairing_client import PairingHttpClient
    from .service_runtime import EnrollmentController
    from .local_control import PrivateUnixControlServer, automatic_poller
    client = PairingHttpClient(origin)  # must be trusted HTTPS
    controller = EnrollmentController(store, client)
    server = PrivateUnixControlServer(runtime_dir / "control.sock", controller)
    serving = threading.Thread(target=server.serve_forever, daemon=True)
    polling = threading.Thread(
        target=automatic_poller, args=(controller, stop_event), daemon=True)
    serving.start()
    polling.start()
    return server, serving, polling


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    stop_event = threading.Event()

    def stop(_signum, _frame):
        stop_event.set()

    signal.signal(signal.SIGINT, stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, stop)
    store = ProtectedCredentialStore(default_identity_path())
    disk = Path("C:/") if sys.platform == "win32" else Path("/")
    controls = None
    # Installed Linux service: the remote origin is provisioned by the
    # administrator-owned systemd configuration, never a user-provided token.
    if sys.platform.startswith("linux"):
        origin = os.environ.get("FLEETLUMA_COORDINATOR_URL", "")
        if origin:
            controls = start_linux_control(store, stop_event, origin)
        else:
            LOG.warning("Agent is idle; pairing disabled until HTTPS origin is installed")
    try:
        run_supervisor(store, disk_path=str(disk), stop_event=stop_event)
    finally:
        stop_event.set()
        if controls is not None:
            server, serving, polling = controls
            server.shutdown()
            server.server_close()
            serving.join(timeout=5)
            polling.join(timeout=5)


if __name__ == "__main__":
    main()
