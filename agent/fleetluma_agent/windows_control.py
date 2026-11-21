"""FL-40 Windows service control via a locally restricted named pipe.

Security rules:
* A named pipe is created ONLY by the FleetLuma Windows service.
* Its explicit protected DACL grants access to LocalSystem, Administrators,
  and the installed NT SERVICE\\FleetLumaAgent service SID. No Everyone/Users.
* Requests are small, allowlisted, and never include a reporting secret.
* Only trusted local administrators (UAC-elevated setup app) can connect.
* Remote clients are rejected at the pipe transport level.
"""
from __future__ import annotations

import json
import logging
import re
import sys
import threading
from dataclasses import asdict

from .service_runtime import EnrollmentController
from .pairing_client import PairingRejected

LOG = logging.getLogger("fleetluma.agent.windows_control")
PIPE_NAME = r"\\.\pipe\FleetLumaAgent-Control-v1"
MAX_MESSAGE = 1024
_SERVICE_SID = re.compile(r"^S-1-5-80-(?:[0-9]+-){4}[0-9]+$")


class ControlUnavailable(Exception):
    pass


def service_pipe_sddl(service_sid: str) -> str:
    """Protected DACL for a Windows *service SID*, never a username string."""
    if not isinstance(service_sid, str) or not _SERVICE_SID.fullmatch(service_sid):
        raise ValueError("Expected a verified NT SERVICE SID")
    return "D:P(A;;GA;;;SY)(A;;GA;;;BA)(A;;GA;;;" + service_sid + ")"


def dispatch_control(controller: EnrollmentController, raw: bytes) -> bytes:
    """Protocol boundary: no private pairing or reporting tokens in response."""
    try:
        if len(raw) > MAX_MESSAGE or not raw.endswith(b"\n"):
            raise ValueError("Oversized or unterminated command")
        message = json.loads(raw.decode("utf-8"))
        if not isinstance(message, dict) or set(message) != {"command"}:
            raise ValueError("Invalid command shape")
        if message["command"] == "status":
            result = asdict(controller.status())
        elif message["command"] == "begin":
            result = asdict(controller.begin())
        elif message["command"] == "cancel":
            controller.cancel()
            result = asdict(controller.status())
        else:
            raise ValueError("Unknown command")
        # Explicit output allowlist, even if controller changes later.
        result = {key: result.get(key) for key in
                  ("status", "user_code", "verification_uri", "expires_in", "host_id")}
    except (ValueError, OSError, RuntimeError, TypeError, PairingRejected):
        result = {"status": "error", "message": "Pairing action unavailable"}
    payload = json.dumps(result, separators=(",", ":")).encode("utf-8")
    if len(payload) > MAX_MESSAGE:
        payload = b'{"status":"error","message":"Response too large"}'
    return payload + b"\n"


def _windows_modules():
    if sys.platform != "win32":
        raise ControlUnavailable("Windows control requires Windows")
    import pywintypes
    import win32con
    import win32file
    import win32pipe
    import win32security
    import winerror
    return pywintypes, win32con, win32file, win32pipe, win32security, winerror


def private_pipe_attributes():
    """Fail closed unless running inside installed service SID identity."""
    pywintypes, _, _, _, security, _ = _windows_modules()
    service_sid, _, _ = security.LookupAccountName(None, r"NT SERVICE\FleetLumaAgent")
    if not security.CheckTokenMembership(None, service_sid):
        raise PermissionError("Only the installed FleetLuma service can host its control pipe")
    sid_value = security.ConvertSidToStringSid(service_sid)
    sddl = service_pipe_sddl(sid_value)
    descriptor = security.ConvertStringSecurityDescriptorToSecurityDescriptor(
        sddl, security.SDDL_REVISION_1)
    attrs = pywintypes.SECURITY_ATTRIBUTES()
    attrs.SECURITY_DESCRIPTOR = descriptor
    attrs.bInheritHandle = False
    return attrs


class WindowsControlServer:
    """Background accept loop. Requests are serialized and one-shot."""
    def __init__(self, controller: EnrollmentController, security_attributes=None):
        self.controller = controller
        self._stop = threading.Event()
        self.security_attributes = (security_attributes if security_attributes is not None
                                    else private_pipe_attributes())
        self._thread: threading.Thread | None = None

    def serve(self):
        _, _, winfile, pipe, _, winerror = _windows_modules()
        while not self._stop.is_set():
            handle = pipe.CreateNamedPipe(
                PIPE_NAME,
                pipe.PIPE_ACCESS_DUPLEX,
                pipe.PIPE_TYPE_MESSAGE | pipe.PIPE_READMODE_MESSAGE |
                pipe.PIPE_WAIT | pipe.PIPE_REJECT_REMOTE_CLIENTS,
                1, 2048, 2048, 2000, self.security_attributes,
            )
            connected = False
            try:
                try:
                    pipe.ConnectNamedPipe(handle, None)
                    connected = True
                except Exception as exc:
                    if getattr(exc, "winerror", None) == winerror.ERROR_PIPE_CONNECTED:
                        connected = True
                    elif not self._stop.is_set():
                        LOG.warning("Windows pairing client connection failed")
                if connected and not self._stop.is_set():
                    try:
                        _, data = winfile.ReadFile(handle, MAX_MESSAGE + 1)
                        reply = dispatch_control(self.controller, data)
                        winfile.WriteFile(handle, reply)
                        winfile.FlushFileBuffers(handle)
                    except Exception:
                        LOG.warning("Windows pairing command failed")
            finally:
                if connected:
                    try:
                        pipe.DisconnectNamedPipe(handle)
                    except Exception:
                        pass
                winfile.CloseHandle(handle)

    def start(self):
        if self._thread is not None:
            raise RuntimeError("Control server already running")
        self._thread = threading.Thread(target=self.serve, name="fleetluma-pipe", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        # Wake a blocking ConnectNamedPipe without publishing a token or
        # invoking a destructive operation. The service has pipe access.
        try:
            windows_command("status", timeout_ms=200)
        except (OSError, ControlUnavailable):
            pass
        if self._thread is not None:
            self._thread.join(timeout=4)


def windows_command(action: str, timeout_ms: int = 3000) -> dict:
    """Called by an elevated local setup application, never via a cloud API."""
    if action not in {"status", "begin", "cancel"}:
        raise ValueError("Command not permitted")
    _, wincon, winfile, pipe, _, _ = _windows_modules()
    pipe.WaitNamedPipe(PIPE_NAME, timeout_ms)
    handle = winfile.CreateFile(
        PIPE_NAME, wincon.GENERIC_READ | wincon.GENERIC_WRITE,
        0, None, wincon.OPEN_EXISTING, 0, None)
    try:
        winfile.WriteFile(handle, json.dumps({"command": action}).encode("utf-8") + b"\n")
        _, reply = winfile.ReadFile(handle, MAX_MESSAGE + 1)
        if len(reply) > MAX_MESSAGE or not reply.endswith(b"\n"):
            raise ControlUnavailable("Invalid local control response")
        result = json.loads(reply.decode("utf-8"))
        if not isinstance(result, dict) or "status" not in result:
            raise ControlUnavailable("Invalid local control response")
        return result
    finally:
        winfile.CloseHandle(handle)
