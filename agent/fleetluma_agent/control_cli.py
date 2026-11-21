"""Privileged local Linux control helper for headless FleetLuma pairing.

Intended for sudo/pkexec or an administrator-approved setup companion.
Never accepts or prints reporting tokens or the device polling secret.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .local_control import command


def main() -> int:
    if not sys.platform.startswith("linux"):
        raise RuntimeError("This helper supports Linux only")
    parser = argparse.ArgumentParser(description="Control the local FleetLuma service")
    parser.add_argument("command", choices=("status", "begin", "cancel"))
    args = parser.parse_args()
    try:
        response = command(Path("/run/fleetluma/control.sock"), args.command)
    except (OSError, ValueError, RuntimeError):
        print("FleetLuma local control is unavailable or requires administrator access.", file=sys.stderr)
        return 2
    status = response.get("status")
    if status == "waiting":
        print("Pairing code:", response.get("user_code", "unavailable"))
        print("Open:", response.get("verification_uri", "https://fleetluma-web.vercel.app"))
        print("Seconds remaining:", response.get("expires_in", 0))
    elif status == "paired":
        print("Agent paired. Monitoring service can start automatically.")
    elif status == "not_paired":
        print("No paired device. Run 'begin' from an approved local administrator session.")
    elif status == "error":
        print("Pairing action unavailable. Check the local service.", file=sys.stderr)
        return 2
    else:
        print("Pairing status:", status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
