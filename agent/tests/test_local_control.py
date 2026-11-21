"""FL-39 restricted local pairing control, Linux-only smoke tests."""
import json
import os
import stat
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from fleetluma_agent.service_runtime import PublicPairingStatus


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux AF_UNIX transport")
class LinuxControlTests(unittest.TestCase):
    def setUp(self):
        from fleetluma_agent.local_control import (
            PrivateUnixControlServer, command, LocalControlError,
        )
        self.Server = PrivateUnixControlServer
        self.command = command
        self.LocalControlError = LocalControlError

    def test_restrict_socket_and_expose_only_safe_display_data(self):
        class Fake:
            def __init__(self):
                self.waiting = False
                self.cancelled = False
            def status(self):
                return PublicPairingStatus(
                    status="waiting" if self.waiting else "not_paired",
                    user_code="ABCD-7294" if self.waiting else None,
                    verification_uri="https://fleetluma.example/devices/pair" if self.waiting else None,
                    expires_in=600 if self.waiting else None)
            def begin(self):
                self.waiting=True
                return self.status()
            def cancel(self):
                self.cancelled=True
                self.waiting=False
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            root.chmod(0o700)
            socket_file = root / "control.sock"
            fake = Fake()
            server = self.Server(socket_file, fake)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                self.assertEqual(stat.S_IMODE(socket_file.stat().st_mode),0o600)
                response=self.command(socket_file,"status")
                self.assertEqual(response["status"],"not_paired")
                response=self.command(socket_file,"begin")
                self.assertEqual(response["user_code"],"ABCD-7294")
                self.assertNotIn("device_code",response)
                self.assertNotIn("report_token",response)
                self.assertNotIn("private",json.dumps(response))
                response=self.command(socket_file,"cancel")
                self.assertEqual(response["status"],"not_paired")
                self.assertTrue(fake.cancelled)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
            self.assertFalse(socket_file.exists())

    def test_rejects_unprotected_runtime_folder(self):
        class Fake:
            pass
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            root.chmod(0o755)
            with self.assertRaises(self.LocalControlError):
                self.Server(root/"control.sock", Fake())

    def test_does_not_replace_existing_files_or_symlinks(self):
        class Fake:
            pass
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            root.chmod(0o700)
            path=root/"control.sock"
            path.write_text("no overwrite",encoding="utf-8")
            with self.assertRaises(self.LocalControlError):
                self.Server(path,Fake())
            self.assertEqual(path.read_text(encoding="utf-8"),"no overwrite")
            path.unlink()
            path.symlink_to(root/"destination")
            with self.assertRaises(self.LocalControlError):
                self.Server(path,Fake())

    def test_command_is_whitelisted(self):
        with self.assertRaises(ValueError):
            self.command(Path("/does/not/exist"),"read-token")

    def test_automatic_polling_uses_existing_controller(self):
        from fleetluma_agent.local_control import automatic_poller
        stop=threading.Event()
        class Fake:
            calls=0
            def status(self):
                return PublicPairingStatus(status="waiting")
            def poll_once(self):
                self.calls+=1
                stop.set()
        fake=Fake()
        automatic_poller(fake,stop,interval=0.01)
        self.assertEqual(fake.calls,1)


if __name__ == "__main__":
    unittest.main()
