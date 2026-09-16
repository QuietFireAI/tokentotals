import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import config_manager
import proxy_server


class _FakeResponse:
    def model_dump(self):
        return {"ok": True}


class _FakeChunk:
    def model_dump_json(self):
        return '{"chunk":true}'


async def _fake_stream():
    yield _FakeChunk()


class TurnReceiptBindingTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        app_dir = Path(self.tempdir.name) / ".tokentotals"
        self.paths = patch.multiple(config_manager, APP_DIR=app_dir, CONFIG_FILE=app_dir / "config.json", STATE_FILE=app_dir / "state.json")
        self.paths.start()
        self.addCleanup(self.paths.stop)
        with config_manager._DATA_LOCK:
            config_manager._INFLIGHT_RESERVATIONS.clear()
            config_manager._SETTLED_RESERVATION_IDS.clear()
        self.addCleanup(self._clear_ephemeral_state)
        config_manager.init_files()
        conf = config_manager.get_config()
        conf["daily_budget_limit_usd"] = 100.0
        config_manager.save_config(conf)
        self.client = TestClient(proxy_server.app)

    def _clear_ephemeral_state(self):
        with config_manager._DATA_LOCK:
            config_manager._INFLIGHT_RESERVATIONS.clear()
            config_manager._SETTLED_RESERVATION_IDS.clear()

    def test_nonstream_response_header_matches_server_owned_receipt_id(self):
        captured = {}
        async def upstream(**kwargs):
            captured.update(kwargs)
            return _FakeResponse()
        with patch.object(proxy_server, "preflight_input_estimate", return_value=(0.01, "test")), patch.object(proxy_server.litellm, "acompletion", side_effect=upstream):
            response = self.client.post("/v1/chat/completions", headers={"authorization": "Bearer test", "x-thread-id": "thread-binding"}, json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hello"}]})
        receipt_id = response.headers.get("x-tokentotals-receipt-id")
        self.assertTrue(receipt_id)
        self.assertEqual(receipt_id, captured["litellm_metadata"][proxy_server.RESERVATION_METADATA_KEY])
        self.assertEqual(response.json(), {"ok": True})

    def test_stream_response_header_matches_server_owned_receipt_id(self):
        captured = {}
        async def upstream(**kwargs):
            captured.update(kwargs)
            return _fake_stream()
        with patch.object(proxy_server, "preflight_input_estimate", return_value=(0.01, "test")), patch.object(proxy_server.litellm, "acompletion", side_effect=upstream):
            response = self.client.post("/v1/chat/completions", headers={"authorization": "Bearer test", "x-thread-id": "thread-binding"}, json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hello"}], "stream": True})
        receipt_id = response.headers.get("x-tokentotals-receipt-id")
        self.assertTrue(receipt_id)
        self.assertEqual(receipt_id, captured["litellm_metadata"][proxy_server.RESERVATION_METADATA_KEY])
        self.assertIn('data: {"chunk":true}', response.text)
        self.assertIn('data: [DONE]', response.text)

    def test_client_cannot_spoof_server_receipt_id(self):
        captured = {}
        async def upstream(**kwargs):
            captured.update(kwargs)
            return _FakeResponse()
        with patch.object(proxy_server, "preflight_input_estimate", return_value=(0.01, "test")), patch.object(proxy_server.litellm, "acompletion", side_effect=upstream):
            response = self.client.post(
                "/v1/chat/completions",
                headers={
                    "authorization": "Bearer test",
                    "x-thread-id": "thread-binding",
                    "x-tokentotals-receipt-id": "attacker-controlled",
                },
                json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hello"}]},
            )
        receipt_id = response.headers.get("x-tokentotals-receipt-id")
        self.assertTrue(receipt_id)
        self.assertNotEqual(receipt_id, "attacker-controlled")
        self.assertEqual(receipt_id, captured["litellm_metadata"][proxy_server.RESERVATION_METADATA_KEY])

    def test_failed_upstream_has_no_receipt_binding(self):
        async def upstream(**kwargs):
            raise RuntimeError("provider unavailable")
        with patch.object(proxy_server, "preflight_input_estimate", return_value=(0.01, "test")), patch.object(proxy_server.litellm, "acompletion", side_effect=upstream):
            response = self.client.post(
                "/v1/chat/completions",
                headers={"authorization": "Bearer test"},
                json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hello"}]},
            )
        self.assertEqual(response.status_code, 502)
        self.assertIsNone(response.headers.get("x-tokentotals-receipt-id"))
        self.assertEqual(config_manager.get_inflight_reserved_usd(), 0.0)

    def test_cors_exposes_receipt_header_to_browser_clients(self):
        async def upstream(**kwargs):
            return _FakeResponse()
        with patch.object(proxy_server, "preflight_input_estimate", return_value=(0.01, "test")), patch.object(proxy_server.litellm, "acompletion", side_effect=upstream):
            response = self.client.post(
                "/v1/chat/completions",
                headers={
                    "authorization": "Bearer test",
                    "origin": "http://example.test",
                },
                json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hello"}]},
            )
        exposed = response.headers.get("access-control-expose-headers", "").lower()
        self.assertIn("x-tokentotals-receipt-id", exposed)

    def test_stream_does_not_inject_receipt_text_into_provider_content(self):
        async def upstream(**kwargs):
            return _fake_stream()
        with patch.object(proxy_server, "preflight_input_estimate", return_value=(0.01, "test")), patch.object(proxy_server.litellm, "acompletion", side_effect=upstream):
            response = self.client.post(
                "/v1/chat/completions",
                headers={"authorization": "Bearer test"},
                json={
                    "model": "gpt-4o",
                    "messages": [{"role": "user", "content": "hello"}],
                    "stream": True,
                },
            )
        self.assertNotIn("TURN RECEIPT", response.text)
        self.assertNotIn("TokenTotals estimate", response.text)
        self.assertIn('data: {"chunk":true}', response.text)


if __name__ == "__main__":
    unittest.main()
