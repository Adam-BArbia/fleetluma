# FL-40 — Windows local pairing and setup contract

The Windows monitoring service and native setup UI use only a **local, versioned Windows named pipe**: `\\\\.\\pipe\\FleetLumaAgent-Control-v1`. There is no localhost HTTP endpoint.

## Approval flow

1. An administrator installs the native FleetLuma service under its pinned service identity and enables the service SID with `sc.exe sidtype FleetLumaAgent unrestricted`.
2. The installer sets the private NTFS ACLs on `%PROGRAMDATA%\\FleetLuma\\private`; it must **not** grant a desktop user read access to `identity.bin`. The same service identity must perform all Windows DPAPI operations.
3. The **local configuration app is elevated** (Windows UAC) for pairing and troubleshooting. Its ordinary-user process does not get administrator rights implicitly; Windows named-pipe permissions deny it access until explicit elevation.
4. The Windows service creates the pipe with a protected ACL allowing only `SYSTEM`, local `Administrators`, and its resolved `NT SERVICE\\FleetLumaAgent` service SID. Remote connections are rejected with `PIPE_REJECT_REMOTE_CLIENTS`.
5. The setup app issues one allowlisted JSON command: `status`, `begin`, `cancel`. The service validates the input and returns only public pairing state and the visible 8-character user code. It **never sends** the device-code polling secret or reporting token over IPC.
6. The operator signs in on the separate FleetLuma dashboard and approves the code there. The service polls the private enrollment coordinator and stores the new approved identity using service-scoped DPAPI. Monitoring resumes after approval.

## Native implementation boundary

- `fleetluma_agent/windows_control.py`: protected named-pipe server and minimal privileged client.
- `fleetluma_agent/windows_setup.py`: native Tk Windows setup interface. It is not a packaged executable yet.
- `fleetluma_agent/windows_service.py`: Windows SCM adapter which runs control, approval polling, and monitor supervisor.
- `fleetluma_agent/secure_state.py`: service-account-bound DPAPI credential storage.
- `fleetluma_agent/service_runtime.py`: private pairing/polling and reporting state machine.

**Installer work still outstanding:** signed/frozen Windows executables; tested SCM registration; UAC manifest for setup UI; dedicated service identity/ACL creation; upgrade, uninstall, repair and rollback; antivirus/SmartScreen validation; clean Windows 11 VM installation, reboot, pairing, revoke, and rollback. The UI is a source-level implementation until this complete.

**Security requirements for release:**

- Never use anonymous, Everyone, Users, or Authenticated Users on the pipe DACL or private token directory.
- Do not allow installation to silently downgrade to an insecure shared-token, localhost HTTP, or unprotected file mode.
- Ensure `CheckTokenMembership` confirms the installed service SID before the pipe starts; fail closed otherwise.
- Do not show reporting tokens or private polling secrets in the setup UI, Windows logs, command-line arguments, saved UI settings, issue trackers or diagnostics.
- Do not change the service account without explicitly handling DPAPI recovery through new pairing.
- Pairing server endpoints remain production-disabled until rollout gates are fulfilled.

This is **not** yet a distributable plug-and-play Windows installer and does not change the existing TUFFEST pilot.
