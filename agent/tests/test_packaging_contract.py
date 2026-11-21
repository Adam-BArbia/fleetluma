"""Service packaging source-level contract checks; not an installer test."""
import configparser
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PackagingContractTests(unittest.TestCase):
    def test_linux_service_has_restricted_identity_and_storage(self):
        unit = ROOT / "packaging/linux/fleetluma-agent.service"
        text = unit.read_text(encoding="utf-8")
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(text)
        service = parser["Service"]
        self.assertEqual(service["User"], "fleetluma")
        self.assertEqual(service["Group"], "fleetluma")
        self.assertEqual(service["StateDirectory"], "fleetluma")
        self.assertEqual(service["StateDirectoryMode"], "0700")
        self.assertEqual(service["UMask"], "0077")
        self.assertEqual(service["NoNewPrivileges"], "true")
        self.assertEqual(service["ProtectSystem"], "strict")
        self.assertEqual(service["ProtectHome"], "true")
        self.assertEqual(service["Restart"], "on-failure")
        self.assertIn("AF_INET", service["RestrictAddressFamilies"])
        self.assertNotIn("FLEETLUMA_AGENT_TOKEN", text)
        self.assertNotIn("FLEETLUMA_DATABASE_URL", text)

    def test_windows_service_wrapper_names_scm_and_no_plaintext_secret(self):
        code = (ROOT / "fleetluma_agent/windows_service.py").read_text(
            encoding="utf-8")
        self.assertIn('FleetLumaAgent', code)
        self.assertIn("SvcStop", code)
        self.assertIn("SvcDoRun", code)
        self.assertIn("ProtectedCredentialStore", code)
        self.assertNotIn("FLEETLUMA_DATABASE_URL", code)
        self.assertNotIn("FLEETLUMA_AGENT_TOKEN", code)


if __name__ == "__main__":
    unittest.main()
