import unittest
from unittest.mock import patch, MagicMock
from fleetluma_agent import collector
from fleetluma_agent.main import load_config, send_report


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

    @patch("fleetluma_agent.main.request.urlopen")
    def test_authenticated_post(self, mock_open):
        mock_response = MagicMock()
        mock_response.status = 202
        mock_response.__enter__.return_value = mock_response
        mock_open.return_value = mock_response
        with patch("fleetluma_agent.main.json.load", return_value={"status": "accepted"}):
            result = send_report("http://127.0.0.1:8000", "secret-token", {"sampled_at": "now"})
        req = mock_open.call_args.args[0]
        self.assertEqual(req.get_header("Authorization"), "Bearer secret-token")
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(result["status"], "accepted")


if __name__ == "__main__":
    unittest.main()
