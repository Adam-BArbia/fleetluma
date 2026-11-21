"""FL-33 agent pairing transport: only HTTPS, bounded bodies, no token leakage."""
import io
import hashlib
import json
import unittest
from urllib import error, request

from fleetluma_agent.pairing_client import (
    PairingHttpClient, PairingRejected, generate_reporting_secret,
    verified_https_origin,
)


class Response:
    def __init__(self, status, payload=b""):
        self.status = status
        self.body = io.BytesIO(payload)

    def read(self, n=-1):
        return self.body.read(n)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class Opener:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def open(self, req, timeout=8):
        self.requests.append(req)
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


class PairingTransportTests(unittest.TestCase):
    def test_https_is_required_no_credentials_or_paths(self):
        for value in (
            "http://fleetluma.example", "https://user:pass@fleetluma.example",
            "https://fleetluma.example/path", "https://fleetluma.example?token=bad",
            "https://localhost", "file:///etc/passwd",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                verified_https_origin(value)
        self.assertEqual(
            verified_https_origin("https://fleetluma.example/"),
            "https://fleetluma.example")

    def test_approval_does_not_send_reporting_secret_to_server(self):
        secret = generate_reporting_secret()
        reply = {"device_code": "a" * 43, "user_code": "ABCD-7294",
                 "verification_uri": "https://fleetluma.example/devices/pair",
                 "expires_in": 600, "interval": 5}
        opener = Opener([
            Response(201, json.dumps(reply).encode()),
            Response(200, b'{"status":"pending"}'),
            Response(200, b'{"status":"paired","host_id":"host","workspace_id":"workspace"}'),
            Response(204),
        ])
        client = PairingHttpClient("https://fleetluma.example", opener=opener)
        ticket = client.start(hostname="TUFFEST", platform="windows",
                              version="0.1.0", report_token=secret,
                              capabilities=["cpu", "ram", "disk"])
        self.assertEqual(ticket.user_code, "ABCD-7294")
        self.assertIsNone(client.poll(ticket))
        self.assertEqual(client.poll(ticket).host_id, "host")
        client.cancel(ticket)
        req = opener.requests[0]
        payload = json.loads(req.data.decode())
        self.assertEqual(
            payload["report_token_sha256"],
            hashlib.sha256(secret.encode()).hexdigest())
        self.assertNotIn(secret, req.data.decode())
        self.assertNotIn(secret, repr(ticket))
        self.assertTrue(all(r.full_url.startswith("https://") for r in opener.requests))

    def test_http_error_exposes_only_status(self):
        unauthorized = error.HTTPError(
            "https://fleetluma.example", 401,
            "secret server error text", {}, io.BytesIO(b"secret response"))
        opener = Opener([unauthorized])
        client = PairingHttpClient("https://fleetluma.example", opener=opener)
        with self.assertRaises(PairingRejected) as ctx:
            client.start(hostname="machine", platform="linux",
                         version="0.1.0", report_token=generate_reporting_secret(),
                         capabilities=[])
        self.assertEqual(ctx.exception.status, 401)
        self.assertNotIn("secret", str(ctx.exception))

    def test_malformed_response_is_rejected(self):
        bad = {"user_code": "ABCD-7294", "device_code": "abcd",
               "verification_uri": "http://evil", "expires_in": 600,
               "interval": 0}
        client = PairingHttpClient(
            "https://fleetluma.example",
            opener=Opener([Response(201, json.dumps(bad).encode())]))
        with self.assertRaises(ValueError):
            client.start(hostname="machine", platform="linux",
                         version="0.1.0", report_token=generate_reporting_secret(),
                         capabilities=[])


if __name__ == "__main__":
    unittest.main()
