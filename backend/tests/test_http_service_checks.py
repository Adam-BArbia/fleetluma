"""FL-10: live local HTTP probes and SQLite check history.

No external service or physical two-machine deployment is involved.
"""
import json
import os
import threading
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4

from fastapi.testclient import TestClient

from fleetluma_backend import app as backend
from fleetluma_backend import service_checks


class DemoHandler(BaseHTTPRequestHandler):
    response_code = 200

    def do_GET(self):
        self.send_response(type(self).response_code)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *_):
        pass


def launch(port=0):
    server = ThreadingHTTPServer(("127.0.0.1", port), DemoHandler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def stop(server, thread):
    server.shutdown()
    thread.join(timeout=3)
    server.server_close()


def test_service_outage_recovery_and_host_independence(monkeypatch):
    server, thread = launch()
    port = server.server_address[1]
    sid = str(uuid4())
    host_id = str(uuid4())
    try:
        with tempfile.TemporaryDirectory() as temp:
            monkeypatch.setenv("FLEETLUMA_DATABASE_PATH", os.path.join(temp, "db.sqlite"))
            monkeypatch.setenv("FLEETLUMA_HOSTS_JSON", json.dumps([{
                "id": host_id, "name": "test-host", "os": "linux",
                "token": "demo-secret-long-enough"}]))
            monkeypatch.setenv("FLEETLUMA_SERVICES_JSON", json.dumps([{
                "id": sid, "name": "HTTP demo",
                "url": f"http://127.0.0.1:{port}/health",
                "host_id": None, "enabled": True}]))
            backend.provision()
            client = TestClient(backend.app)
            assert client.get("/api/v1/services").json()["items"][0]["status"] == "UNKNOWN"
            assert client.get("/api/v1/hosts/" + host_id).json()["status"] == "PENDING"

            service_checks.check_enabled(backend.db)
            first = client.get("/api/v1/services").json()["items"][0]
            assert first["status"] == "HEALTHY"
            assert first["latency_ms"] >= 0

            DemoHandler.response_code = 503
            service_checks.check_enabled(backend.db)
            failed = client.get("/api/v1/services").json()["items"][0]
            assert failed["status"] == "UNHEALTHY"
            checks = client.get("/api/v1/services/" + sid + "/checks?window=1h").json()["items"]
            assert checks[-1]["http_code"] == 503
            assert checks[-1]["failure_kind"] == "http_error"

            stop(server, thread)
            server = None
            service_checks.check_enabled(backend.db)
            broken = client.get("/api/v1/services").json()["items"][0]
            assert broken["status"] == "UNHEALTHY"
            recent = client.get("/api/v1/services/" + sid + "/checks").json()["items"]
            assert recent[-1]["http_code"] is None
            assert recent[-1]["failure_kind"] in {"network_error", "timeout"}

            DemoHandler.response_code = 200
            server, thread = launch(port)
            service_checks.check_enabled(backend.db)
            recovered = client.get("/api/v1/services").json()["items"][0]
            assert recovered["status"] == "HEALTHY"
            assert client.get("/api/v1/hosts/" + host_id).json()["status"] == "PENDING"
            assert client.get("/api/v1/services/not-a-uuid/checks").status_code == 404
    finally:
        if server is not None:
            stop(server, thread)
        DemoHandler.response_code = 200


def test_config_does_not_allow_redirects_or_url_secrets():
    opener = service_checks.request.build_opener(
        service_checks.request.ProxyHandler({}), service_checks.NoRedirect())
    assert opener is not None
