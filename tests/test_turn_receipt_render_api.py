import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import proxy_server
import turn_ledger


class TurnReceiptRenderApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(proxy_server.app)
        self.receipt = {
            "schema": "tokentotals.turn_receipt",
            "schema_version": 1,
            "receipt_id": "turn-render",
            "turn": {"turn_id": "turn-render", "thread_id": "thread-render"},
        }

    def test_standard_returns_html_and_does_not_load_thread_aggregate(self):
        with patch.object(proxy_server.turn_receipt, "by_id", return_value=self.receipt) as receipt_lookup, \
             patch.object(proxy_server.telemetry_view, "thread_view") as thread_lookup, \
             patch.object(proxy_server.turn_receipt_renderer, "render_html", return_value='<article>standard</article>') as renderer:
            response = self.client.get('/api/turn-receipt/turn-render/render?mode=standard')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers.get('content-type', '').startswith('text/html'))
        self.assertEqual(response.text, '<article>standard</article>')
        receipt_lookup.assert_called_once_with('turn-render')
        thread_lookup.assert_not_called()
        renderer.assert_called_once_with(self.receipt, mode='standard', thread_view=None)

    def test_expanded_loads_current_thread_aggregate(self):
        thread = {"thread_id": "thread-render", "turn_count": 4}
        with patch.object(proxy_server.turn_receipt, "by_id", return_value=self.receipt), \
             patch.object(proxy_server.telemetry_view, "thread_view", return_value=thread) as thread_lookup, \
             patch.object(proxy_server.turn_receipt_renderer, "render_html", return_value='<article>expanded</article>') as renderer:
            response = self.client.get('/api/turn-receipt/turn-render/render?mode=expanded')

        self.assertEqual(response.status_code, 200)
        thread_lookup.assert_called_once_with('thread-render')
        renderer.assert_called_once_with(self.receipt, mode='expanded', thread_view=thread)

    def test_default_mode_is_standard(self):
        with patch.object(proxy_server.turn_receipt, "by_id", return_value=self.receipt), \
             patch.object(proxy_server.telemetry_view, "thread_view") as thread_lookup, \
             patch.object(proxy_server.turn_receipt_renderer, "render_html", return_value='<article>standard</article>') as renderer:
            response = self.client.get('/api/turn-receipt/turn-render/render')

        self.assertEqual(response.status_code, 200)
        thread_lookup.assert_not_called()
        renderer.assert_called_once_with(self.receipt, mode='standard', thread_view=None)

    def test_invalid_mode_is_rejected_before_receipt_lookup(self):
        with patch.object(proxy_server.turn_receipt, "by_id") as lookup:
            response = self.client.get('/api/turn-receipt/turn-render/render?mode=giant')
        self.assertEqual(response.status_code, 400)
        self.assertIn("standard", response.json()["detail"])
        lookup.assert_not_called()

    def test_unknown_turn_returns_404(self):
        with patch.object(proxy_server.turn_receipt, "by_id", return_value=None):
            response = self.client.get('/api/turn-receipt/missing/render')
        self.assertEqual(response.status_code, 404)

    def test_receipt_ledger_corruption_is_visible(self):
        with patch.object(proxy_server.turn_receipt, "by_id", side_effect=turn_ledger.LedgerCorruptionError('bad line 12')):
            response = self.client.get('/api/turn-receipt/turn-render/render')
        self.assertEqual(response.status_code, 500)
        self.assertIn('bad line 12', response.json()['detail'])

    def test_expanded_thread_corruption_is_visible(self):
        with patch.object(proxy_server.turn_receipt, "by_id", return_value=self.receipt), \
             patch.object(proxy_server.telemetry_view, "thread_view", side_effect=turn_ledger.LedgerCorruptionError('bad line 13')):
            response = self.client.get('/api/turn-receipt/turn-render/render?mode=expanded')
        self.assertEqual(response.status_code, 500)
        self.assertIn('bad line 13', response.json()['detail'])


if __name__ == '__main__':
    unittest.main()
