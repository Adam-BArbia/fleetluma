import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fleetluma_backend.provision_agent import provision


@unittest.skipUnless(os.name == "posix", "Provisioning requires Linux or WSL")
class CloudAgentProvisioningTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "FLEETLUMA_MODE": "cloud",
            "FLEETLUMA_DATABASE_URL": "postgresql://unused-test-dsn",
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_secure_per_host_token_file_and_backend_registration(self):
        registered = []

        class Store:
            def provision_host(self, host_id, name, os_name, token):
                registered.append((host_id, name, os_name, token))

        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "agent.json"
            host_id, output = provision(
                "workstation-01", "windows", path, store_factory=Store
            )
            self.assertEqual(output, str(path))
            self.assertTrue(path.is_file())
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["host_id"], host_id)
            self.assertEqual(payload["host_name"], "workstation-01")
            self.assertEqual(payload["os"], "windows")
            self.assertGreaterEqual(len(payload["agent_token"]), 48)
            self.assertEqual(registered, [
                (host_id, "workstation-01", "windows", payload["agent_token"])
            ])

    def test_existing_file_is_never_overwritten(self):
        class Store:
            def provision_host(self, *args):
                raise AssertionError("DB must not be touched")

        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "existing.json"
            path.write_text("existing secret", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                provision("host-01", "linux", path, store_factory=Store)
            self.assertEqual(path.read_text(encoding="utf-8"), "existing secret")

    def test_database_failure_removes_generated_secret_file(self):
        class FailingStore:
            def provision_host(self, *args):
                raise RuntimeError("simulated connection failure")

        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "new.json"
            with self.assertRaises(RuntimeError):
                provision("host-02", "linux", path, store_factory=FailingStore)
            self.assertFalse(path.exists())

    def test_fails_closed_in_local_mode(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(os.environ, {"FLEETLUMA_MODE": "local"}):
                with self.assertRaisesRegex(RuntimeError, "cloud"):
                    provision("host-03", "linux", Path(temp) / "agent.json")
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_rejects_invalid_hostname(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "Host name"):
                provision("../../some/path", "linux", Path(temp) / "agent.json")


if __name__ == "__main__":
    unittest.main()
