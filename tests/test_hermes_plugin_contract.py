import importlib.util
import io
import sys
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


PLUGIN_PATH = Path(__file__).resolve().parents[1] / "integrations" / "hermes" / "turnreceipt" / "__init__.py"


def load_plugin(name="turnreceipt_plugin_test"):
    spec = importlib.util.spec_from_file_location(name, PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Ctx:
    def __init__(self):
        self.hooks = {}

    def register_hook(self, name, callback):
        self.hooks[name] = callback


class HermesPluginContractTests(unittest.TestCase):
    def test_registers_documented_observer_hooks(self):
        plugin = load_plugin("turnreceipt_plugin_hooks")
        ctx = _Ctx()
        with patch.object(plugin, "_install_cli_display_adapter", return_value=True):
            plugin.register(ctx)
        self.assertEqual(
            set(ctx.hooks),
            {"pre_llm_call", "post_api_request", "api_request_error", "post_llm_call", "on_session_finalize"},
        )

    def test_payload_sent_to_tokentotals_excludes_answer_and_prompt(self):
        plugin = load_plugin("turnreceipt_plugin_payload")
        plugin.on_pre_llm_call(
            session_id="session-x",
            turn_id="turn-x",
            task_id="task-x",
            model="gpt-4o-mini",
            platform="cli",
            user_message="DO NOT SEND ME",
            conversation_history=["DO NOT SEND ME EITHER"],
        )
        plugin.on_post_api_request(
            session_id="session-x",
            turn_id="turn-x",
            api_request_id="api-x",
            api_call_count=1,
            provider="openai",
            model="gpt-4o-mini",
            platform="cli",
            usage={"input_tokens": 10, "output_tokens": 5, "prompt_tokens": 10, "total_tokens": 15},
            response={"assistant_message": {"content": "SECRET"}},
        )
        captured = {}

        def fake_post(path, payload):
            captured["path"] = path
            captured["payload"] = payload
            return {"receipt_text_standard": "RECEIPT"}

        with patch.object(plugin, "_post_json", side_effect=fake_post):
            plugin.on_post_llm_call(
                session_id="session-x",
                turn_id="turn-x",
                task_id="task-x",
                model="gpt-4o-mini",
                platform="cli",
                assistant_response="DO NOT SEND THIS ANSWER",
                user_message="DO NOT SEND THIS PROMPT",
            )

        encoded = repr(captured["payload"])
        self.assertEqual(captured["path"], "/api/hermes/turn")
        self.assertNotIn("DO NOT SEND", encoded)
        self.assertNotIn("SECRET", encoded)
        self.assertIn("api-x", encoded)

    def test_cli_wrapper_prints_receipt_after_original_response_panel(self):
        plugin = load_plugin("turnreceipt_plugin_display")
        events = []

        class FakeMixin:
            def _chat_print_response_panel(self, turn, response):
                events.append(("answer", response))

        hermes_cli = types.ModuleType("hermes_cli")
        cli_mixin = types.ModuleType("hermes_cli.cli_chat_turn_mixin")
        cli_mixin.CLIChatTurnMixin = FakeMixin
        old_cli = sys.modules.get("hermes_cli")
        old_mixin = sys.modules.get("hermes_cli.cli_chat_turn_mixin")
        sys.modules["hermes_cli"] = hermes_cli
        sys.modules["hermes_cli.cli_chat_turn_mixin"] = cli_mixin
        try:
            self.assertTrue(plugin._install_cli_display_adapter())
            plugin._queue_display("session-y", "turn-y", "hello world", "TURN RECEIPT\nTurnReceipt.com")
            instance = FakeMixin()
            instance.session_id = "session-y"
            output = io.StringIO()
            with redirect_stdout(output):
                instance._chat_print_response_panel(object(), "hello world")
            self.assertEqual(events, [("answer", "hello world")])
            self.assertIn("TURN RECEIPT", output.getvalue())
            self.assertIn("TurnReceipt.com", output.getvalue())
        finally:
            if old_cli is None:
                sys.modules.pop("hermes_cli", None)
            else:
                sys.modules["hermes_cli"] = old_cli
            if old_mixin is None:
                sys.modules.pop("hermes_cli.cli_chat_turn_mixin", None)
            else:
                sys.modules["hermes_cli.cli_chat_turn_mixin"] = old_mixin

    def test_response_digest_binds_without_storing_answer_text(self):
        plugin = load_plugin("turnreceipt_plugin_digest")
        plugin._queue_display("session-z", "turn-z", "same exact answer", "receipt-z")
        pending = plugin._pop_matching_receipt("session-z", "same exact answer")
        self.assertEqual(pending["turn_id"], "turn-z")
        self.assertEqual(pending["receipt_text"], "receipt-z")
        self.assertNotIn("same exact answer", repr(pending))


if __name__ == "__main__":
    unittest.main()
