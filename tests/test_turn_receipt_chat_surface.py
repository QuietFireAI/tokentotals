import unittest

from fastapi.testclient import TestClient

import proxy_server
import turn_receipt_chat_surface


class TurnReceiptChatSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(proxy_server.app)

    def test_chat_surface_is_served_inside_local_token_totals_app(self):
        response = self.client.get("/chat")
        self.assertEqual(response.status_code, 200)
        self.assertIn("TokenTotals · Turn Receipt Chat", response.text)
        self.assertIn("Turn Receipt appears directly beneath it", response.text)

    def test_chat_surface_uses_server_owned_receipt_binding_and_renderer(self):
        html = turn_receipt_chat_surface.CHAT_HTML
        self.assertIn('const RECEIPT_HEADER = "X-TokenTotals-Receipt-ID"', html)
        self.assertIn('/api/turn-receipt/${encodeURIComponent(receiptId)}/render', html)
        self.assertIn('response.headers.get(RECEIPT_HEADER)', html)
        self.assertIn('slot.innerHTML = await response.text()', html)

    def test_standard_is_default_and_expanded_is_user_selectable(self):
        html = turn_receipt_chat_surface.CHAT_HTML
        self.assertIn('<option value="standard">Standard receipt</option>', html)
        self.assertIn('<option value="expanded">Expanded receipt</option>', html)
        self.assertIn('saved === "expanded" ? "expanded" : "standard"', html)
        self.assertIn('localStorage.setItem(MODE_KEY', html)

    def test_api_key_is_not_persisted_by_chat_surface(self):
        html = turn_receipt_chat_surface.CHAT_HTML
        self.assertIn('type="password"', html)
        self.assertIn('autocomplete="off"', html)
        self.assertNotIn("tokentotals.apiKey", html)
        self.assertNotIn("localStorage.setItem(\"apiKey\"", html)
        self.assertIn("is not written to the Turn Receipt ledger", html)

    def test_model_choices_come_from_runtime_registry_not_static_marketing_copy(self):
        html = turn_receipt_chat_surface.CHAT_HTML
        self.assertIn('fetch("/v1/models"', html)
        self.assertIn("Choose a model from the TokenTotals registry", html)
        self.assertNotIn("gpt-4o", html)
        self.assertNotIn("claude-3", html)

    def test_model_answer_body_is_not_modified_with_receipt_text(self):
        html = turn_receipt_chat_surface.CHAT_HTML
        self.assertIn('body:JSON.stringify({model, messages, stream:false})', html)
        self.assertIn('answer.textContent = text', html)
        self.assertIn('const slot = addReceiptSlot(assistant, receiptId)', html)
        self.assertNotIn('textAnswer +=', html)

    def test_receipt_polling_handles_settlement_lag_without_fake_zero(self):
        html = turn_receipt_chat_surface.CHAT_HTML
        self.assertIn("Settling Turn Receipt", html)
        self.assertIn("response.status !== 404", html)
        self.assertIn("Turn Receipt is still settling", html)
        self.assertNotIn("$0.0000", html)

    def test_new_thread_resets_conversation_but_not_global_page(self):
        html = turn_receipt_chat_surface.CHAT_HTML
        self.assertIn("function resetThread()", html)
        self.assertIn("messages = []", html)
        self.assertIn("threadId = newThreadId()", html)
        self.assertIn("New thread. Ask a question", html)

    def test_no_popup_or_dashboard_is_required_for_receipt_flow(self):
        html = turn_receipt_chat_surface.CHAT_HTML
        self.assertNotIn("window.open", html)
        self.assertNotIn("alert(", html)
        self.assertNotIn("/dashboard", html)
        self.assertIn("tt-chat-receipt-slot", html)


if __name__ == "__main__":
    unittest.main()
