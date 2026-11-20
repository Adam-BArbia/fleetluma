import unittest
from unittest.mock import patch, MagicMock
from fleetluma_agent import collector
from fleetluma_agent.main import load_config, send_report, _validate_coordinator_url, _RejectRedirects


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
    def test_authenticated_post(self, mock_build):
        mock_response = MagicMock()
        mock_response.status = 202
        mock_response.__enter__.return_value = mock_response
        mock_build.return_value.open.return_value = mock_response
        with patch("fleetluma_agent.main.json.load", return_value={"status": "accepted"}):
            result = send_report("http://127.0.0.1:8000", "secret-token", {"sampled_at": "now"})
        req = mock_build.return_value.open.call_args.args[0]
        self.assertEqual(req.get_header("Authorization"), "Bearer secret-token")
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(result["status"], "accepted")

        self.assertIsInstance(mock_build.call_args.args[0], _RejectRedirects)

    def test_cloud_agent_refuses_plain_http(self):
        with self.assertRaises(ValueError):
            load_config({
                "FLEETLUMA_COORDINATOR_URL": "http://127.0.0.1:8000",
                "FLEETLUMA_AGENT_TOKEN": "agent-token-example-123456",
                "FLEETLUMA_AGENT_CLOUD_MODE": "true",
            })

    def test_rejects_remote_http_without_explicit_lab_opt_in(self):
        with self.assertRaises(ValueError):
            load_config({
                "FLEETLUMA_COORDINATOR_URL": "http://192.168.1.10:8000",
                "FLEETLUMA_AGENT_TOKEN": "agent-token-example-123456",
            })
        url, _, _, _ = load_config({
            "FLEETLUMA_COORDINATOR_URL": "http://192.168.1.10:8000",
            "FLEETLUMA_AGENT_TOKEN": "agent-token-example-123456",
            "FLEETLUMA_ALLOW_INSECURE_LAN": "true",
        })
        self.assertEqual(url, "http://192.168.1.10:8000")

    def test_rejects_embedded_credentials_paths_and_non_https_remote(self):
        for url in (
            "https://user:password@fleet.example.com",
            "https://fleet.example.com/other",
            "https://fleet.example.com?token=secret",
            "http://fleet.example.com",
        ):
            with self.assertRaises(ValueError):
                _validate_coordinator_url(url)

    def test_rejects_redirect_replay(self):
        self.assertIsNone(_RejectRedirects().redirect_request(
            None, None, 307, "redirect", {}, "https://unknown.example.com"))



if __name__ == "__main__":
    unittest.main()
