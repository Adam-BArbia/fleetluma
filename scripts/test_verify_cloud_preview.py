import json
import unittest

from scripts.verify_cloud_preview import validate_preview_url, validate_response


class CloudPreviewCheckTests(unittest.TestCase):
    def test_accepts_vercel_https_origin(self):
        self.assertEqual(
            validate_preview_url("https://fleetluma-api-preview.vercel.app/"),
            "https://fleetluma-api-preview.vercel.app",
        )

    def test_denies_other_hosts_insecure_protocols_and_query(self):
        for origin in (
            "http://fleetluma-api.vercel.app",
            "https://evil.example.com",
            "https://fleetluma-api.vercel.app.evil.test",
            "https://fleetluma-api.vercel.app:8443",
            "https://fleetluma-api.vercel.app?token=secret",
            "https://user:password@fleetluma-api.vercel.app",
        ):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                validate_preview_url(origin)

    def test_cloud_health_and_unauthorized_read(self):
        validate_response(
            "/health", 200, json.dumps({"status": "ready", "mode": "cloud"})
        )
        validate_response(
            "/api/v1/hosts", 401, b'{"error":{"code":"UNAUTHORIZED"}}'
        )
        with self.assertRaises(AssertionError):
            validate_response("/api/v1/hosts", 200, b'{"items":[]}')
        with self.assertRaises(AssertionError):
            validate_response("/health", 200, b'{"status":"local"}')


if __name__ == "__main__":
    unittest.main()
