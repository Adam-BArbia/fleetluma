# FL-38 — Operating-system service packaging foundation

**Status: source configuration only. This is NOT a downloadable plug-and-play installer yet.** Do not point end users to these files or deploy until native setup UI, protected local IPC, signed release packaging and clean-machine tests exist.

## Linux (Ubuntu/Debian)

- Target frozen `fleetluma-agent` executable is installed at `/usr/lib/fleetluma/fleetluma-agent`.
- `linux/fleetluma-agent.service` runs as the dedicated `fleetluma` system user under systemd, with `StateDirectory=fleetluma` (0700) and a private identity path `/var/lib/fleetluma/private/identity.bin`.
- Installer must create the service user/group, verify ownership/permissions, install a locked-down agent binary and compatible setup companion, register/unregister `systemd` unit and preserve state across upgrades.
- Do **not** give the ordinary user direct read/write access to the service credential file. Configure a separate restricted local IPC endpoint and elevation/authorization policy for the setup UI before normal enrollment can work.
- Service can safely start unpaired and wait for a new identity. The setup UI/IPC feature is **not yet implemented**.
- Do not enable outgoing arbitrary HTTP targets or remote process execution.

## Windows

- `fleetluma_agent/windows_service.py` contains an SCM adapter requiring **pywin32** and a validated packaged executable.
- Packaged service must run under a fixed dedicated Windows service identity. Installers must create the `%PROGRAMDATA%\\FleetLuma\\private` directory with explicit restricted NTFS ACLs; Windows DPAPI stores the encrypted credential for the **same identity**.
- A service identity change invalidates its CurrentUser DPAPI credential. Repair/re-pair with administrator approval is required; never grant normal users raw service-credential access.
- Installer must register the actual frozen service executable with the Service Control Manager, install the separate configuration companion, and implement clean upgrade/stop/uninstall operations. **Do not call `sc create` on an untested Python script.**
- Future setup companion must use a Windows named pipe with an explicitly audited security descriptor, not an unauthenticated localhost HTTP service.

## Pending release validation

Build frozen Python binaries with pinned dependencies; verify Windows SCM start/stop/reboot and Linux systemd start/stop/reboot on clean machines, automatic reporting, paired-state restoration, revocation, no token leakage, native UI flow, secure local IPC, uninstallation, and signed/reproducible artifacts.

**No installer or service was installed on TUFFEST by this change.**
