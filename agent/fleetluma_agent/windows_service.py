"""Windows Service Control Manager integration for a frozen agent executable.

Installed under a dedicated service account with protected ProgramData ACLs.
Requires pywin32 on Windows. This is a source adapter, NOT an installer.
"""
from __future__ import annotations

import os
import sys
import threading

if sys.platform == "win32":
    import servicemanager
    import win32event
    import win32service
    import win32serviceutil

    from .service_entry import default_identity_path, run_supervisor
    from .secure_state import ProtectedCredentialStore
    from .pairing_client import PairingHttpClient
    from .service_runtime import EnrollmentController
    from .pairing_poller import automatic_poller
    from .windows_control import WindowsControlServer

    class FleetLumaWindowsService(win32serviceutil.ServiceFramework):
        _svc_name_ = "FleetLumaAgent"
        _svc_display_name_ = "FleetLuma Monitoring Agent"
        _svc_description_ = "FleetLuma device monitoring and secure enrollment"

        def __init__(self, args):
            super().__init__(args)
            self.stop_event = threading.Event()
            self.scm_event = win32event.CreateEvent(None, 0, 0, None)

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            self.stop_event.set()
            win32event.SetEvent(self.scm_event)

        def SvcDoRun(self):
            servicemanager.LogInfoMsg("FleetLuma monitoring service started")
            store = ProtectedCredentialStore(default_identity_path("win32"))
            # The installed service's coordinator origin is a public HTTPS URL,
            # not a secret. The private reporting token comes from DPAPI only.
            origin = os.environ.get(
                "FLEETLUMA_COORDINATOR_URL",
                "https://fleetluma-api.vercel.app",
            )
            client = PairingHttpClient(origin)
            controller = EnrollmentController(store, client)
            pipe = WindowsControlServer(controller)
            poller = threading.Thread(
                target=automatic_poller,
                args=(controller, self.stop_event),
                name="fleetluma-windows-poll",
                daemon=True,
            )
            try:
                pipe.start()
                poller.start()
                run_supervisor(store, disk_path="C:/", stop_event=self.stop_event)
            finally:
                self.stop_event.set()
                pipe.stop()
                if poller.is_alive():
                    poller.join(timeout=5)
                servicemanager.LogInfoMsg("FleetLuma monitoring service stopped")


def main():
    if sys.platform != "win32":
        raise RuntimeError("Windows SCM wrapper must run on Windows")
    import win32serviceutil
    if sys.argv[1:] == ["--self-test"]:
        # Exercises the same native imports from inside the frozen binary.
        # Does not install, start, or connect to any service.
        from .windows_control import private_pipe_attributes
        from .secure_state import ProtectedCredentialStore
        from .service_runtime import EnrollmentController
        assert callable(private_pipe_attributes)
        assert ProtectedCredentialStore is not None
        assert EnrollmentController is not None
        print("FleetLuma Windows service imports OK")
        return
    if getattr(sys, "frozen", False):
        # This binary is dedicated to the SCM. Always dispatch when frozen;
        # Windows SCM may supply arguments that must not trigger CLI handling.
        import servicemanager
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(FleetLumaWindowsService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(FleetLumaWindowsService)


if __name__ == "__main__":
    main()
