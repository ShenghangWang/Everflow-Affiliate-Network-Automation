import os
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from backend import app as app_module
from backend.domain import Workflow


class APITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        app_module.workflow = Workflow(str(Path(self.tmp.name) / "api.sqlite3"))
        self.client = TestClient(app_module.app)

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def test_T12_connected_api(self):
        self.assertEqual(self.client.get("/api/health").json()["mode"], "synthetic-mock")
        self.assertEqual(self.client.post("/api/reset").status_code, 200)
        self.assertEqual(self.client.post("/api/leads/L001/draft").status_code, 200)
        self.assertEqual(self.client.post("/api/leads/L001/dispatch").json()["leads"][0]["stage"], "contacted")
        state = self.client.post("/api/leads/L001/reply", json={"text": "I am interested", "event_id": "api-1"}).json()
        self.assertEqual(state["leads"][0]["stage"], "handoff")
        self.assertEqual(state["issues"][0]["owner"], "Demo BD owner")

    def test_T11_host_origin_and_secret_boundary(self):
        self.assertEqual(self.client.get("/api/state", headers={"host": "evil.example"}).status_code, 403)
        self.assertEqual(self.client.post("/api/reset", headers={"origin": "https://evil.example"}).status_code, 403)
        self.assertEqual(self.client.post("/api/reset", headers={"origin": "http://127.0.0.1:5173"}).status_code, 200)
        state = self.client.get("/api/state").json()
        self.assertNotIn("api_key", str(state).lower())
        self.assertFalse(state["mode"]["live_effects"])

    def test_payload_schema_and_live_recipient_rejected(self):
        self.assertEqual(self.client.post("/api/leads/L001/reply", json={"text": "hi", "event_id": "x", "execute": "shell"}).status_code, 400)
        self.assertEqual(self.client.post("/api/leads/L001/edit", json={"recipient": "someone@real.com"}).status_code, 400)
        self.assertEqual(self.client.post("/api/tick", json={"advance_hours": -1}).status_code, 400)
        self.assertEqual(self.client.post("/api/policy", json={"scope": "live"}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
