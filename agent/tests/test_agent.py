import unittest
from unittest.mock import patch, MagicMock
from fleetluma_agent import collector
from fleetluma_agent.main import NoRedirect, load_config, send_report


class AgentTests(unittest.TestCase):
    def test_report_matches_contract(self):
        report = collector.build_report("/", include_processes=False)
        self.assertIn("sampled_at", report)
        for key in ("cpu_pct", "ram_used_bytes", "ram_total_bytes",
                    "disk_path", "disk_used_bytes", "disk_total_bytes"):
            self.assertIn(key, report["metrics"])
        self.assertNotIn("processes", report)

    def test_config_needs_token(self):
        with self.assertRaises(ValueError):
            load_config({"FLEETLUMA_COORDINATOR_URL": "http://127.0.0.1:8000",
                         "FLEETLUMA_AGENT_TOKEN": "REPLACE_ME"})

    @patch("fleetluma_agent.main.request.build_opener")
    def test_authenticated_post(self, mock_builder):
        mock_response = MagicMock()
        mock_response.status = 202
        mock_response.__enter__.return_value = mock_response
        mock_builder.return_value.open.return_value = mock_response
        with patch("fleetluma_agent.main.json.load", return_value={"status": "accepted"}):
            result = send_report("http://127.0.0.1:8000", "secret-token", {"sampled_at": "now"})
        req = mock_builder.return_value.open.call_args.args[0]
        self.assertEqual(req.get_header("Authorization"), "Bearer secret-token")
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(result["status"], "accepted")

    def test_public_http_blocked_without_explicit_lab_opt_in(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            load_config({
                "FLEETLUMA_COORDINATOR_URL": "http://api.example.com",
                "FLEETLUMA_AGENT_TOKEN": "random-token-at-least-16-characters",
                "FLEETLUMA_DISK_PATH": "/",
            })

    def test_cloud_mode_disallows_even_local_http(self):
        with self.assertRaisesRegex(ValueError, "requires HTTPS"):
            load_config({
                "FLEETLUMA_COORDINATOR_URL": "http://127.0.0.1:8000",
                "FLEETLUMA_AGENT_TOKEN": "random-token-at-least-16-characters",
                "FLEETLUMA_DISK_PATH": "/",
                "FLEETLUMA_MODE": "cloud",
            })

    def test_local_lab_http_requires_explicit_opt_in(self):
        config = load_config({
            "FLEETLUMA_COORDINATOR_URL": "http://192.168.192.1:8000",
            "FLEETLUMA_AGENT_TOKEN": "random-token-at-least-16-characters",
            "FLEETLUMA_DISK_PATH": "/",
            "FLEETLUMA_ALLOW_INSECURE_LAN": "true",
        })
        self.assertEqual(config[0], "http://192.168.192.1:8000")

    def test_agent_redirect_never_forwarded(self):
        from urllib import request
        initial = request.Request("https://api.example.com/api/v1/agent/reports",
                                  headers={"Authorization": "Bearer secret-token"})
        self.assertIsNone(NoRedirect().redirect_request(
            initial, None, 302, "Found", {}, "https://attacker.example/collect"
        ))

    @patch("fleetluma_agent.main.request.build_opener")
    def test_sender_uses_no_redirect_handler(self, mock_builder):
        response = MagicMock(status=202)
        response.__enter__.return_value = response
        mock_builder.return_value.open.return_value = response
        with patch("fleetluma_agent.main.json.load", return_value={"status": "accepted"}):
            send_report("https://api.example.com", "token-is-at-least-16", {"sampled_at": "now"})
        self.assertTrue(any(isinstance(item, NoRedirect)
                            for item in mock_builder.call_args.args))


if __name__ == "__main__":
    unittest.main()
