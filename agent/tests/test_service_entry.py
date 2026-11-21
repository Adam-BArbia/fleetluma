"""FL-37 supervisor starts from durable identity and locks revoked token."""
import threading
import unittest
from unittest.mock import patch
from uuid import uuid4

from fleetluma_agent.secure_state import AgentIdentity, CredentialMissing
from fleetluma_agent.service_entry import default_identity_path, run_supervisor
from fleetluma_agent.service_runtime import NeedsRepair
from fleetluma_agent.pairing_client import PairingStarted


def identity(token=None):
    return AgentIdentity(
        host_id=str(uuid4()), workspace_id=str(uuid4()),
        report_token=token or ("service-private-token-" + uuid4().hex),
        api_origin="https://fleetluma.example")


class FakeStore:
    def __init__(self, credential=None):
        self.credential = credential
    def load(self):
        if self.credential is None:
            raise CredentialMissing()
        return self.credential


class InstantEvent:
    def __init__(self):
        self.stopped = False
        self.wait_count = 0
    def is_set(self):
        return self.stopped
    def wait(self, seconds):
        self.wait_count += 1
        if self.wait_count > 3:
            self.stopped = True
        return self.stopped


class SupervisorTests(unittest.TestCase):
    def test_known_installation_paths(self):
        self.assertTrue(default_identity_path("linux").as_posix().endswith("var/lib/fleetluma/private/identity.bin"))
        with patch.dict("os.environ", {"PROGRAMDATA": "C:/ProgramData"}):
            self.assertIn("FleetLuma", str(default_identity_path("win32")))
        with self.assertRaises(RuntimeError):
            default_identity_path("darwin")

    def test_missing_credentials_do_not_start_monitoring(self):
        event = InstantEvent()
        starts = []
        run_supervisor(
            FakeStore(), disk_path="/", stop_event=event,
            reporter=lambda *a, **k: starts.append(1))
        self.assertEqual(starts, [])

    def test_revoked_token_never_retried_without_repair(self):
        token = "private-256bit-token-no-send-" + uuid4().hex
        store = FakeStore(identity(token))
        event = InstantEvent()
        attempts = []
        def rejected(_store, **kwargs):
            attempts.append(_store.credential.report_token)
            raise NeedsRepair()
        run_supervisor(store, disk_path="/", stop_event=event, reporter=rejected)
        self.assertEqual(attempts, [token])

    def test_new_approved_credential_can_restart_after_repair(self):
        first = identity()
        second = identity()
        store = FakeStore(first)
        stop = threading.Event()
        calls = []
        def reporter(_store, **kwargs):
            calls.append(_store.credential.report_token)
            if len(calls) == 1:
                store.credential = second
                raise NeedsRepair()
            stop.set()
        run_supervisor(store, disk_path="/", stop_event=stop, reporter=reporter)
        self.assertEqual(calls, [first.report_token, second.report_token])

    def test_secret_repr_is_redacted(self):
        creds = identity()
        self.assertNotIn(creds.report_token, repr(creds))
        ticket = PairingStarted(
            user_code="ABCD-7294", device_code="unique-private-code-not-for-logs",
            verification_uri="https://fleetluma.example", interval=5, expires_in=600)
        self.assertNotIn(ticket.device_code, repr(ticket))


if __name__ == "__main__":
    unittest.main()
