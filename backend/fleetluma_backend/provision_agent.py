"""Privileged, POSIX-only cloud agent enrollment (never exposed over HTTP).

Run from backend/ with a valid FLEETLUMA_DATABASE_URL in a private shell:
  FLEETLUMA_MODE=cloud python -m fleetluma_backend.provision_agent \
      --name workstation-01 --os windows --token-file ~/.config/fleetluma/workstation-01.json

The new output file contains a secret. It is created exclusively with 0600
permissions and never echoed to the terminal. Transfer it to the intended host
using a trusted channel; remove the source after provisioning is complete.
"""
import argparse
import json
import os
import re
import secrets
from pathlib import Path
from uuid import uuid4

from .postgres_store import PostgresStore


HOST_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{1,63}$")


def provision(name, os_name, destination, store_factory=PostgresStore):
    if os.environ.get("FLEETLUMA_MODE") != "cloud":
        raise RuntimeError("Provisioning requires FLEETLUMA_MODE=cloud")
    if not os.environ.get("FLEETLUMA_DATABASE_URL"):
        raise RuntimeError("Provisioning requires a private PostgreSQL DSN")
    if os.name != "posix":
        raise RuntimeError("Provisioning requires POSIX 0600 permissions; use Linux/WSL")
    if not HOST_NAME_RE.fullmatch(name):
        raise ValueError("Host name must be 2-64 safe ASCII characters")
    if os_name not in ("windows", "linux"):
        raise ValueError("Host OS must be windows or linux")

    token_path = Path(destination).expanduser()
    if not token_path.parent.is_dir():
        raise ValueError("Token output parent directory must already exist")
    # Never overwrite another host's credential, and reject preexisting symlinks.
    host_id = str(uuid4())
    token = secrets.token_urlsafe(48)
    payload = json.dumps({"host_id": host_id, "host_name": name,
                          "os": os_name, "agent_token": token}) + "\n"
    descriptor = os.open(token_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    enrolled = False
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.chmod(token_path, 0o600)
        store_factory().provision_host(host_id, name, os_name, token)
        enrolled = True
    finally:
        if not enrolled:
            # No durable credential is left behind when DB enrollment fails.
            token_path.unlink(missing_ok=True)
    # Deliberately do not return/print the token or database credentials.
    return host_id, str(token_path)


def main():
    parser = argparse.ArgumentParser(description="Provision a private FleetLuma cloud agent token")
    parser.add_argument("--name", required=True)
    parser.add_argument("--os", choices=("windows", "linux"), required=True)
    parser.add_argument("--token-file", required=True)
    args = parser.parse_args()
    try:
        host_id, file_path = provision(args.name, args.os, args.token_file)
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(2, "Provisioning failed; inspect private configuration and output path.\n")
    print("Host enrolled:", host_id)
    print("Credential file (private, 0600):", file_path)
    print("Copy securely to the intended host, restrict access, then remove the source copy.")


if __name__ == "__main__":
    main()
