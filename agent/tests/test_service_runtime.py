"""FL-36 service-owned enrollment and reporting state tests."""
import threading
import unittest
from unittest.mock import patch
from urllib import error
from uuid import uuid4

from fleetluma_agent.pairing_client import (
    PairingAccepted, PairingRejected, PairingStarted,
)
from fleetluma_agent.secure_state import AgentIdentity, CredentialMissing
from fleetluma_agent.service_runtime import (
    EnrollmentController, NeedsRepair, run_paired_service,
)


class FakeStore:
    def __init__(self):
        self.identity = None
        self.saved = 0

    def load(self):
        if self.identity is None:
            raise CredentialMissing()
        return self.identity

    def store(self, identity):
        if self.identity:
            raise FileExistsError()
        self.identity = identity
        self.saved += 1


class FakeClient:
    origin = "https://fleetluma.example"

    def __init__(self):
        self.starts = []
        self.polls = 0
        self.cancels = 0
        self.paired = False

    def start(self, **kwargs):
        self.starts.append(kwargs)
        return PairingStarted(
            user_code="ABCD-7294",
            device_code="private-session-secret-256bit-do-not-share",
            verification_uri="https://fleetluma.example/devices/pair",
            interval=5, expires_in=600,
        )

    def poll(self, ticket):
        self.polls += 1
        if self.paired:
            return PairingAccepted(str(uuid4()), str(uuid4()))
        return None

    def cancel(self, ticket):
        self.cancels += 1


class ServiceRuntimeTests(unittest.TestCase):
    def test_enrollment_hides_private_token_and_persists_after_approval(self):
        now = [100.0]
        store = FakeStore()
        client = FakeClient()
        controller = EnrollmentController(store, client, clock=lambda: now[0])
        with patch("fleetluma_agent.service_runtime.platform.system", return_value="Windows"):
            with patch("fleetluma_agent.service_runtime.socket.gethostname", return_value="TUFFEST"):
                preview = controller.begin()
        self.assertEqual(preview.user_code, "ABCD-7294")
        self.assertEqual(preview.status, "waiting")
        self.assertNotIn("device_code", str(preview))
        self.assertNotIn("report_token", str(preview))
        self.assertEqual(client.starts[0]["platform"], "windows")
        # Polling may not begin before the server-prescribed interval.
        controller.poll_once()
        self.assertEqual(client.polls, 0)
        now[0] += 5
        controller.poll_once()
        self.assertEqual(client.polls, 1)
        client.paired = True
        now[0] += 5
        approved = controller.poll_once()
        self.assertEqual(approved.status, "paired")
        self.assertEqual(store.saved, 1)
        self.assertEqual(len(store.identity.report_token), 43)
        self.assertEqual(controller.status().status, "paired")
        with self.assertRaises(ValueError):
            controller.begin()

    def test_user_cancel_destroys_private_pending_state(self):
        now = [100.0]
        store, client = FakeStore(), FakeClient()
        controller = EnrollmentController(store, client, clock=lambda: now[0])
        with patch("fleetluma_agent.service_runtime.platform.system", return_value="Linux"):
            controller.begin()
        controller.cancel()
        self.assertEqual(client.cancels, 1)
        self.assertEqual(controller.status().status, "not_paired")
        with self.assertRaises(ValueError):
            controller.poll_once()

    def test_denied_or_expired_code_cannot_create_identity(self):
        for status in (403, 410):
            with self.subTest(status=status):
                now = [100.0]
                client, store = FakeClient(), FakeStore()
                controller = EnrollmentController(store, client, clock=lambda: now[0])
                with patch("fleetluma_agent.service_runtime.platform.system", return_value="Linux"):
                    controller.begin()
                def reject(ticket):
                    raise PairingRejected(status)
                client.poll = reject
                now[0] += 5
                state = controller.poll_once()
                self.assertEqual(state.status, "denied" if status == 403 else "expired")
                self.assertEqual(controller.status().status, "not_paired")
                self.assertEqual(store.saved, 0)

    def test_reporting_stops_immediately_after_revoked_token(self):
        store = FakeStore()
        store.identity = AgentIdentity(
            host_id=str(uuid4()), workspace_id=str(uuid4()),
            report_token="unique-service-credential-" + uuid4().hex,
            api_origin="https://fleetluma.example")
        calls = [0]
        def revoked(url, token, report):
            calls[0] += 1
            raise error.HTTPError(
                url, 401, "Unauthorized", {}, None,
            )
        with self.assertRaises(NeedsRepair):
            run_paired_service(
                store, "/", interval=10,
                report_sender=revoked,
                collector=lambda disk, include_processes: {"sampled_at": "now"},
            )
        self.assertEqual(calls[0], 1)

    def test_reporting_uses_protected_identity_and_honors_stop(self):
        store = FakeStore()
        store.identity = AgentIdentity(
            host_id=str(uuid4()), workspace_id=str(uuid4()),
            report_token="unique-service-credential-" + uuid4().hex,
            api_origin="https://fleetluma.example")
        event = threading.Event()
        calls = []
        def send(url, token, report):
            calls.append((url, token))
            event.set()
        run_paired_service(
            store, "/", stop_event=event, report_sender=send,
            collector=lambda disk, include_processes: {"sampled_at": "now"})
        self.assertEqual(calls, [(
            "https://fleetluma.example", store.identity.report_token)])
        self.assertTrue(event.is_set())


if __name__ == "__main__":
    unittest.main()
