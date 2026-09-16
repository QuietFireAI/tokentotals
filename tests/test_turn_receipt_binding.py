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


if __name__ == "__main__":
    unittest.main()
