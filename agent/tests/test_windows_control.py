"""Windows named-pipe protocol and authorization tests.

Only protocol decisions are platform independent. ACL and native API checks
run on Windows CI with pywin32, with no service installed on a CI machine.
"""
import json
import sys
import unittest
from dataclasses import dataclass
from unittest.mock import patch

from fleetluma_agent.windows_control import (
    MAX_MESSAGE, PIPE_NAME, ControlUnavailable, dispatch_control,
    service_pipe_sddl, windows_command,
)
from fleetluma_agent.service_runtime import PublicPairingStatus


class FakeController:
    def __init__(self):
        self.paired = False
        self.cancelled = False

    def status(self):
        return PublicPairingStatus(status="not_paired")

    def begin(self):
        return PublicPairingStatus(
            status="waiting", user_code="ABCD-7294",
            verification_uri="https://fleetluma.example/devices/pair",
            expires_in=600,
        )

    def cancel(self):
        self.cancelled = True


class WindowsPipeProtocolTests(unittest.TestCase):
    def test_very_restrictive_sid_allowlist(self):
        sid = "S-1-5-80-1-2-3-4-5"
        rule = service_pipe_sddl(sid)
        self.assertEqual(
            rule, "D:P(A;;GA;;;SY)(A;;GA;;;BA)(A;;GA;;;S-1-5-80-1-2-3-4-5)")
        for invalid in ("", "S-1-5-32-545", "S-1-1-0", "WD",
                        "S-1-5-80-1-2-3-4-5)(A;;GA;;;WD)"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                service_pipe_sddl(invalid)

    def test_private_session_secret_does_not_cross_ipc(self):
        reply = dispatch_control(FakeController(), b'{"command":"begin"}\n')
        body = json.loads(reply)
        self.assertEqual(body["user_code"], "ABCD-7294")
        self.assertNotIn("device_code", body)
        self.assertNotIn("report_token", body)
        self.assertNotIn("private", reply.decode())

    def test_status_cancel_and_reject_unknown(self):
        controller = FakeController()
        self.assertEqual(
            json.loads(dispatch_control(controller,b'{"command":"status"}\n'))["status"],
            "not_paired")
        self.assertEqual(
            json.loads(dispatch_control(controller,b'{"command":"cancel"}\n'))["status"],
            "not_paired")
        self.assertTrue(controller.cancelled)
        for payload in (b'{"command":"read_token"}\n',
                        b'{"command":"begin","token":"secret"}\n',
                        b'not-json\n', b'{"command":"begin"}',
                        b'{"command":"begin"}\n' + b'x'*MAX_MESSAGE):
            with self.subTest(payload=payload[:30]):
                result = json.loads(dispatch_control(controller,payload))
                self.assertEqual(result["status"], "error")

    def test_non_windows_transport_fails_closed(self):
        if sys.platform == "win32":
            self.skipTest("Native behavior covered by Windows CI ACL tests")
        with self.assertRaises(ControlUnavailable):
            windows_command("status")
        with self.assertRaises(ValueError):
            windows_command("reveal-token")

    @unittest.skipUnless(sys.platform == "win32", "Native Windows ACL test")
    def test_sddl_parser_produces_expected_admin_and_service_sids(self):
        import win32security
        descriptor = win32security.ConvertStringSecurityDescriptorToSecurityDescriptor(
            service_pipe_sddl("S-1-5-80-1-2-3-4-5"),
            win32security.SDDL_REVISION_1)
        dacl = descriptor.GetSecurityDescriptorDacl()
        self.assertEqual(dacl.GetAceCount(), 3)
        self.assertEqual(
            [win32security.ConvertSidToStringSid(dacl.GetAce(i)[2]) for i in range(3)],
            ["S-1-5-18", "S-1-5-32-544", "S-1-5-80-1-2-3-4-5"])


if __name__ == "__main__":
    unittest.main()
