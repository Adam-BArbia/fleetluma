"""FL-35 secure agent credential store acceptance on Windows and Linux."""
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from fleetluma_agent.secure_state import (
    AgentIdentity, CredentialMissing, ProtectedCredentialStore,
)


class SecureStoreTests(unittest.TestCase):
    def identity(self):
        return AgentIdentity(
            host_id=str(uuid4()), workspace_id=str(uuid4()),
            report_token="very-long-privately-generated-agent-token-" + uuid4().hex,
            api_origin="https://fleetluma.example",
        )

    def test_roundtrip_no_overwrite_and_private_storage(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            if os.name == "posix":
                parent.chmod(0o700)
            store = ProtectedCredentialStore(parent / "agent-identity.bin")
            with self.assertRaises(CredentialMissing):
                store.load()
            identity = self.identity()
            store.store(identity)
            self.assertEqual(store.load(), identity)
            with self.assertRaises(FileExistsError):
                store.store(self.identity())
            if os.name == "posix":
                self.assertEqual(stat.S_IMODE(store.path.stat().st_mode), 0o600)
                self.assertEqual(stat.S_IMODE(parent.stat().st_mode), 0o700)
            if sys.platform == "win32":
                self.assertNotIn(identity.report_token.encode(), store.path.read_bytes())
            store.clear_after_explicit_revoke()
            with self.assertRaises(CredentialMissing):
                store.load()

    @unittest.skipUnless(os.name == "posix", "POSIX filesystem policy")
    def test_rejects_world_readable_parent_and_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.chmod(0o755)
            store = ProtectedCredentialStore(root / "identity")
            with self.assertRaises(PermissionError):
                store.store(self.identity())
            root.chmod(0o700)
            store.store(self.identity())
            store.path.chmod(0o644)
            with self.assertRaises(PermissionError):
                store.load()

    def test_rejects_invalid_identity(self):
        with self.assertRaises(ValueError):
            AgentIdentity(
                host_id="not-uuid", workspace_id=str(uuid4()),
                report_token="my-secret-is-very-long-and-private-in-tests-only",
                api_origin="https://fleetluma.example",
            )
        with self.assertRaises(ValueError):
            AgentIdentity(
                host_id=str(uuid4()), workspace_id=str(uuid4()),
                report_token="short", api_origin="https://fleetluma.example",
            )

    def test_symlink_file_rejected(self):
        if os.name != "posix":
            self.skipTest("POSIX symlink test")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.chmod(0o700)
            target = root / "target"
            target.write_text("should remain unmodified", encoding="utf-8")
            link = root / "identity"
            link.symlink_to(target)
            store = ProtectedCredentialStore(link)
            with self.assertRaises(OSError):
                store.store(self.identity())
            with self.assertRaises(OSError):
                store.load()
            self.assertEqual(target.read_text(), "should remain unmodified")


if __name__ == "__main__":
    unittest.main()
