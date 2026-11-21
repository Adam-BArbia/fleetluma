"""FL-39 Linux local control: restricted Unix socket, never TCP/HTTP.

Only the dedicated service UID or root may access this control socket.
Desktop setup integration must invoke a separate authorized/elevated helper;
ordinary unprivileged users cannot connect directly. No device session
credential or reporting token is exposed over IPC.
"""
from __future__ import annotations

import json
import logging
import os
import socket
import socketserver
import stat
import threading
from dataclasses import asdict
from pathlib import Path

from .pairing_client import PairingRejected
from .service_runtime import EnrollmentController

LOG = logging.getLogger("fleetluma.agent.local_control")


class LocalControlError(Exception):
    pass


def _private_parent(path: Path) -> None:
    parent = path.parent
    if parent.is_symlink() or not parent.is_dir():
        raise LocalControlError("Runtime control directory must already exist")
    info = parent.stat()
    if info.st_uid != os.geteuid() or (stat.S_IMODE(info.st_mode) & 0o077):
        raise LocalControlError("Runtime directory requires service-owned 0700 permissions")


class _ControlHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        # Bounded read with a timeout to avoid a local client holding workers.
        self.request.settimeout(3.0)
        raw = self.rfile.readline(1025)
        if len(raw) > 1024 or not raw.endswith(b"\n"):
            self._reply({"status": "error", "message": "Invalid command"})
            return
        try:
            msg = json.loads(raw.decode("utf-8"))
            if not isinstance(msg, dict) or set(msg) != {"command"}:
                raise ValueError("Unexpected fields")
            operation = msg["command"]
            if operation == "status":
                state = self.server.controller.status()
            elif operation == "begin":
                state = self.server.controller.begin()
            elif operation == "cancel":
                self.server.controller.cancel()
                state = self.server.controller.status()
            else:
                raise ValueError("Unknown operation")
            self._reply(asdict(state))
        except (ValueError, PairingRejected, OSError, RuntimeError) as exc:
            # Do not include exception details: HTTP bodies / credential
            # payloads / local transport internals never reach an IPC peer.
            LOG.warning("Rejected local pairing action: %s", type(exc).__name__)
            self._reply({"status": "error", "message": "Pairing action unavailable"})

    def _reply(self, body: dict) -> None:
        payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
        if len(payload) > 1024:
            payload = b'{"status":"error","message":"Response too large"}'
        self.wfile.write(payload + b"\n")


class PrivateUnixControlServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, path: Path, controller: EnrollmentController):
        if os.name != "posix":
            raise RuntimeError("Unix control socket is for Linux only")
        self.path = Path(path)
        _private_parent(self.path)
        if self.path.exists() or self.path.is_symlink():
            raise LocalControlError("Refusing to replace an existing control socket")
        self.controller = controller
        super().__init__(str(self.path), _ControlHandler)
        try:
            os.chmod(self.path, 0o600)
            info = self.path.stat()
            if not stat.S_ISSOCK(info.st_mode):
                raise LocalControlError("Expected Unix socket")
            if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600:
                raise LocalControlError("Socket permissions are unsafe")
        except BaseException:
            super().server_close()
            self.path.unlink(missing_ok=True)
            raise

    def server_close(self) -> None:
        super().server_close()
        self.path.unlink(missing_ok=True)


def command(path: Path, action: str, timeout: float = 3.0) -> dict:
    """Client-side IPC for a separately privileged local setup helper."""
    if action not in {"status", "begin", "cancel"}:
        raise ValueError("Invalid local command")
    if os.name != "posix":
        raise RuntimeError("Unix control socket requires Linux")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        client.connect(str(path))
        client.sendall(json.dumps({"command": action}).encode("utf-8") + b"\n")
        chunks = bytearray()
        while b"\n" not in chunks:
            portion = client.recv(1025 - len(chunks))
            if not portion or len(chunks) + len(portion) > 1024:
                raise LocalControlError("Invalid control response")
            chunks.extend(portion)
        result = json.loads(chunks.split(b"\n", 1)[0].decode("utf-8"))
        if not isinstance(result, dict) or "status" not in result:
            raise LocalControlError("Invalid control response")
        return result


def automatic_poller(controller: EnrollmentController,
                     stop_event: threading.Event, interval: float = 1.0) -> None:
    """No user-level shell needed while waiting for dashboard approval."""
    while not stop_event.is_set():
        try:
            if controller.status().status == "waiting":
                controller.poll_once()
        except (PairingRejected, OSError, RuntimeError, ValueError) as exc:
            LOG.warning("Pairing poll failed (%s)", type(exc).__name__)
        stop_event.wait(interval)
