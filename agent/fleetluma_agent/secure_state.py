"""FL-35: private local credential persistence for the agent service identity.

Windows: DPAPI CurrentUser encryption (service account is the only decryptor).
Linux: private 0700 directory and exclusive 0600 file owned by service UID.
This module is for the **service process**, not an unprivileged setup UI.
The setup UI must eventually use a protected IPC channel; direct file sharing
between accounts or plaintext command-line credentials is prohibited.
"""
from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from uuid import UUID


class CredentialMissing(Exception):
    pass


@dataclass(frozen=True)
class AgentIdentity:
    host_id: str
    workspace_id: str
    report_token: str = field(repr=False)
    api_origin: str

    def __post_init__(self):
        from .pairing_client import verified_https_origin
        UUID(self.host_id)
        UUID(self.workspace_id)
        if len(self.report_token) < 40:
            raise ValueError("Reporting credential is too short")
        verified_https_origin(self.api_origin)


def _protect(raw: bytes) -> bytes:
    if sys.platform != "win32":
        return raw
    return _dpapi(raw, decrypt=False)


def _unprotect(raw: bytes) -> bytes:
    if sys.platform != "win32":
        return raw
    return _dpapi(raw, decrypt=True)


def _dpapi(data: bytes, *, decrypt: bool) -> bytes:
    """Call Win32 DPAPI under the service's account; no LocalMachine flag."""
    if sys.platform != "win32":
        raise OSError("Windows DPAPI is unavailable")
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(DATA_BLOB), wintypes.LPCWSTR,
        ctypes.POINTER(DATA_BLOB), ctypes.c_void_p,
        ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DATA_BLOB)]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(DATA_BLOB), ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(DATA_BLOB), ctypes.c_void_p,
        ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DATA_BLOB)]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p

    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source = DATA_BLOB(len(data), buffer)
    destination = DATA_BLOB()
    # CRYPTPROTECT_UI_FORBIDDEN is mandatory in a background service.
    UI_FORBIDDEN = 0x1
    if decrypt:
        call = crypt32.CryptUnprotectData
        ok = call(ctypes.byref(source), None, None, None,
                  None, UI_FORBIDDEN, ctypes.byref(destination))
    else:
        call = crypt32.CryptProtectData
        ok = call(ctypes.byref(source), "FleetLuma agent credential",
                  None, None, None, UI_FORBIDDEN, ctypes.byref(destination))
    if not ok:
        raise OSError("Windows service identity cannot access the saved credential")
    try:
        if not destination.pbData:
            raise OSError("DPAPI returned no encrypted data")
        return ctypes.string_at(destination.pbData, destination.cbData)
    finally:
        kernel32.LocalFree(destination.pbData)


class ProtectedCredentialStore:
    """May only be instantiated in the trusted agent service process."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def _check_dir(self) -> None:
        parent = self.path.parent
        if parent.is_symlink():
            raise OSError("Refusing credential directory symlink")
        if not parent.exists():
            parent.mkdir(mode=0o700, parents=True)
        if not parent.is_dir():
            raise OSError("Private credential parent must be a directory")
        if os.name == "posix":
            mode = stat.S_IMODE(parent.stat().st_mode)
            if mode & 0o077:
                raise PermissionError("Credential directory must be private (0700)")
            if parent.stat().st_uid != os.geteuid():
                raise PermissionError("Credential directory must be owned by service UID")

    def store(self, identity: AgentIdentity) -> None:
        self._check_dir()
        if self.path.is_symlink():
            raise OSError("Refusing credential file symlink")
        if self.path.exists():
            raise FileExistsError("Agent already paired; explicit revoke/re-pair required")
        raw = json.dumps(asdict(identity), separators=(",", ":")).encode("utf-8")
        payload = _protect(raw)
        # Exclusive file creation prevents accidental overwrite; no secret in argv.
        descriptor = os.open(str(self.path), os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                             0o600)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            if os.name == "posix":
                os.chmod(self.path, 0o600)
        except BaseException:
            self.path.unlink(missing_ok=True)
            raise

    def load(self) -> AgentIdentity:
        self._check_dir()
        if self.path.is_symlink():
            raise OSError("Refusing credential file symlink")
        if not self.path.exists():
            raise CredentialMissing("Agent is not paired")
        if os.name == "posix":
            info = self.path.stat()
            if (stat.S_IMODE(info.st_mode) & 0o077 or
                    info.st_uid != os.geteuid() or
                    not stat.S_ISREG(info.st_mode)):
                raise PermissionError("Agent credentials have unsafe permissions")
        with self.path.open("rb") as handle:
            payload = handle.read(4097)
        if len(payload) > 4096:
            raise OSError("Unexpectedly large encrypted identity")
        try:
            value = json.loads(_unprotect(payload).decode("utf-8"))
            return AgentIdentity(**value)
        except (UnicodeError, TypeError, ValueError, KeyError) as exc:
            raise OSError("Stored identity is corrupt") from None

    def clear_after_explicit_revoke(self) -> None:
        self._check_dir()
        if self.path.is_symlink():
            raise OSError("Refusing credential file symlink")
        self.path.unlink(missing_ok=True)
