"""Regression tests for the seven proxy bugs found in the Nov 2026 fact check.

Each test class fails on main at fa32a65 and passes with the fixes.
"""

import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import config_manager
import proxy_server
import turn_ledger

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8080"


class _FakeResponse:
    def model_dump(self):
        return {"ok": True}


class _IsolatedStateMixin:
    budget = 100.0

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        app_dir = Path(self.tempdir.name) / ".tokentotals"
        self.ledger_file = app_dir / "turns.jsonl"
        self.paths = patch.multiple(
            config_manager,
            APP_DIR=app_dir,
            CONFIG_FILE=app_dir / "config.json",
            STATE_FILE=app_dir / "state.json",
        )
        self.paths.start()
        self.addCleanup(self.paths.stop)
        self.ledger_override = patch.object(turn_ledger, "_LEDGER_FILE_OVERRIDE", self.ledger_file)
        self.ledger_override.start()
        self.addCleanup(self.ledger_override.stop)
        self._clear_ephemeral_state()
        self.addCleanup(self._clear_ephemeral_state)
        config_manager.init_files()
        conf = config_manager.get_config()
        conf["daily_budget_limit_usd"] = self.budget
        config_manager.save_config(conf)
        self.client = TestClient(proxy_server.app, base_url=BASE_URL)

    def _clear_ephemeral_state(self):
        with config_manager._DATA_LOCK:
            config_manager._INFLIGHT_RESERVATIONS.clear()
            config_manager._SETTLED_RESERVATION_IDS.clear()
        with turn_ledger._LEDGER_LOCK:
            turn_ledger._SEEN_LEDGER_PATH = None
            turn_ledger._SEEN_TURN_IDS = None

    def _control_headers(self, **extra):
        headers = {proxy_server.CONTROL_TOKEN_HEADER: proxy_server.CONTROL_TOKEN}
        headers.update(extra)
        return headers


# --- Bug 1: spend was never recorded -----------------------------------------


class Bug1SpendIsRecordedThroughRealLiteLLMTests(_IsolatedStateMixin, unittest.TestCase):
    """Goes through the real litellm.acompletion path; only the network is mocked.

    The older tests replaced acompletion and hand-called track_cost_callback,
    which is why it went unnoticed that LiteLLM never calls a synchronous
    success_callback for acompletion.
    """

    def _real_litellm_with_mock_response(self, text):
        real_acompletion = proxy_server.litellm.acompletion

        async def acompletion(**kwargs):
            return await real_acompletion(mock_response=text, **kwargs)

        return patch.object(proxy_server.litellm, "acompletion", side_effect=acompletion)

    def _assert_turn_settled(self, receipt_id, thread_id):
        state = config_manager.get_state()
        self.assertGreater(state["current_spend_usd"], 0.0)
        self.assertEqual(state["total_requests"], 1)
        self.assertEqual(state["unpriced_turn_count"], 0)
        self.assertEqual(config_manager.get_inflight_reserved_usd(), 0.0)

        records = turn_ledger.read_turns(thread_id=thread_id)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["turn_id"], receipt_id)
        self.assertIsNotNone(records[0]["estimated_cost_usd"])
        self.assertAlmostEqual(records[0]["estimated_cost_usd"], state["current_spend_usd"])

        receipt = self.client.get(f"/api/turn-receipt/{receipt_id}")
        self.assertEqual(receipt.status_code, 200)

    def test_nonstream_request_lands_in_spend_ledger_and_receipt(self):
        with self._real_litellm_with_mock_response("hello from the mock provider"):
            response = self.client.post(
                "/v1/chat/completions",
                headers={"authorization": "Bearer sk-test", "x-thread-id": "bug1"},
                json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
            )
        self.assertEqual(response.status_code, 200, response.text)
        receipt_id = response.headers.get(proxy_server.RECEIPT_ID_HEADER)
        self.assertTrue(receipt_id)
        self._assert_turn_settled(receipt_id, "bug1")

    def test_stream_request_lands_in_spend_ledger_and_receipt(self):
        with self._real_litellm_with_mock_response("streamed hello from the mock provider"):
            response = self.client.post(
                "/v1/chat/completions",
                headers={"authorization": "Bearer sk-test", "x-thread-id": "bug1-stream"},
                json={
                    "model": "gpt-4o",
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": True,
                },
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("data: [DONE]", response.text)
        receipt_id = response.headers.get(proxy_server.RECEIPT_ID_HEADER)
        self.assertTrue(receipt_id)
        self._assert_turn_settled(receipt_id, "bug1-stream")

    def test_failed_settlement_still_releases_reservation(self):
        async def upstream(**kwargs):
            return _FakeResponse()

        with patch.object(proxy_server, "preflight_input_estimate", return_value=(0.25, "test")), \
             patch.object(proxy_server.litellm, "acompletion", side_effect=upstream), \
             patch.object(proxy_server, "track_cost_callback", side_effect=RuntimeError("boom")):
            response = self.client.post(
                "/v1/chat/completions",
                headers={"authorization": "Bearer sk-test"},
                json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(config_manager.get_inflight_reserved_usd(), 0.0)

    def test_stream_rebuild_keeps_resolved_service_tier(self):
        from litellm.types.utils import ModelResponseStream

        base = {"id": "c", "object": "chat.completion.chunk", "created": 1, "model": "gpt-4o-2024-08-06", "service_tier": "default"}
        chunks = [
            ModelResponseStream(**dict(base, choices=[{"index": 0, "delta": {"content": "Hi"}, "finish_reason": None}])),
            ModelResponseStream(**dict(base, choices=[{"index": 0, "delta": {}, "finish_reason": "stop"}])),
        ]
        built = proxy_server.litellm.stream_chunk_builder(chunks, messages=[{"role": "user", "content": "hi"}])
        proxy_server._carry_stream_service_tier(built, chunks)
        self.assertEqual(getattr(built, "service_tier", None), "default")

    def test_proxy_no_longer_relies_on_sync_success_callback(self):
        self.assertNotIn(proxy_server.track_cost_callback, list(proxy_server.litellm.success_callback or []))


# --- Bug 2: open CORS and unauthenticated control routes ----------------------


class Bug2ControlRoutesAndBrowserAccessTests(_IsolatedStateMixin, unittest.TestCase):
    budget = 10.0

    def test_control_routes_refuse_requests_without_token(self):
        for route in ("/api/boost", "/api/unlock"):
            with self.subTest(route=route):
                response = self.client.post(route)
                self.assertEqual(response.status_code, 403)
        response = self.client.post("/api/turn-notice/config", json={"reminder_threshold_usd": 1.0})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(config_manager.get_config()["daily_budget_limit_usd"], 10.0)
        self.assertIsNone(config_manager.get_config()["turn_notice_threshold_usd"])

    def test_control_routes_refuse_wrong_token(self):
        response = self.client.post(
            "/api/boost",
            headers={proxy_server.CONTROL_TOKEN_HEADER: "not-the-token"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(config_manager.get_config()["daily_budget_limit_usd"], 10.0)

    def test_control_route_works_with_token_from_same_origin(self):
        response = self.client.post(
            "/api/boost",
            headers=self._control_headers(origin=BASE_URL),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(config_manager.get_config()["daily_budget_limit_usd"], 15.0)

    def test_control_route_refuses_other_loopback_origin_even_with_token(self):
        response = self.client.post(
            "/api/boost",
            headers=self._control_headers(origin="http://localhost:3000"),
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(config_manager.get_config()["daily_budget_limit_usd"], 10.0)

    def test_foreign_web_page_cannot_post_to_proxy(self):
        called = []

        async def upstream(**kwargs):
            called.append(kwargs)
            return _FakeResponse()

        with patch.object(proxy_server, "preflight_input_estimate", return_value=(0.01, "test")), \
             patch.object(proxy_server.litellm, "acompletion", side_effect=upstream):
            for route in ("/v1/chat/completions", "/api/boost", "/api/unlock"):
                with self.subTest(route=route):
                    response = self.client.post(
                        route,
                        headers={"origin": "http://evil.example", "content-type": "text/plain"},
                        content='{"model": "gpt-4o", "messages": []}',
                    )
                    self.assertEqual(response.status_code, 403)
        self.assertEqual(called, [])
        self.assertEqual(config_manager.get_config()["daily_budget_limit_usd"], 10.0)

    def test_cors_does_not_grant_foreign_origins(self):
        response = self.client.get("/api/status", headers={"origin": "http://evil.example"})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.headers.get("access-control-allow-origin"))
        self.assertIsNone(response.headers.get("access-control-allow-credentials"))

        preflight = self.client.options(
            "/api/boost",
            headers={
                "origin": "http://evil.example",
                "access-control-request-method": "POST",
                "access-control-request-headers": proxy_server.CONTROL_TOKEN_HEADER,
            },
        )
        self.assertNotEqual(preflight.headers.get("access-control-allow-origin"), "http://evil.example")
        self.assertNotEqual(preflight.headers.get("access-control-allow-origin"), "*")

    def test_dns_rebinding_host_is_refused(self):
        for path in ("/dashboard", "/api/status"):
            with self.subTest(path=path):
                response = self.client.get(path, headers={"host": "attacker.example:8080"})
                self.assertEqual(response.status_code, 400)

    def test_dashboard_carries_token_and_sends_it_on_control_calls(self):
        html = self.client.get("/dashboard").text
        self.assertIn(proxy_server.CONTROL_TOKEN, html)
        self.assertNotIn("__TOKENTOTALS_CONTROL_TOKEN__", html)
        self.assertIn("fetch('/api/boost', {method:'POST', headers:controlHeaders()})", html)
        self.assertEqual(html.count("headers:controlHeaders({'Content-Type':'application/json'})"), 2)


# --- Bug 3: client-supplied routing/credential fields ------------------------


class Bug3RequestFieldAllowListTests(_IsolatedStateMixin, unittest.TestCase):
    def test_routing_and_credential_fields_are_refused_before_upstream(self):
        called = []

        async def upstream(**kwargs):
            called.append(kwargs)
            return _FakeResponse()

        dangerous = {
            "api_base": "http://attacker.example/v1",
            "base_url": "http://attacker.example/v1",
            "api_key": "sk-attacker",
            "api_version": "2024-01-01",
            "custom_llm_provider": "openai",
            "extra_headers": {"x-forward": "1"},
            "headers": {"x-forward": "1"},
            "mock_response": "free fake answer",
            "aws_access_key_id": "x",
            "vertex_credentials": "x",
            "fallbacks": ["gpt-4o-mini"],
            "metadata": {"tokentotals_reservation_id": "spoof"},
        }
        with patch.object(proxy_server, "preflight_input_estimate", return_value=(0.01, "test")), \
             patch.object(proxy_server.litellm, "acompletion", side_effect=upstream):
            for key, value in dangerous.items():
                with self.subTest(field=key):
                    response = self.client.post(
                        "/v1/chat/completions",
                        headers={"authorization": "Bearer sk-user"},
                        json={
                            "model": "gpt-4o",
                            "messages": [{"role": "user", "content": "hi"}],
                            key: value,
                        },
                    )
                    self.assertEqual(response.status_code, 400)
                    self.assertIn(key, response.json()["detail"])
        self.assertEqual(called, [])
        self.assertEqual(config_manager.get_inflight_reserved_usd(), 0.0)
        self.assertEqual(config_manager.get_state()["current_spend_usd"], 0.0)

    def test_normal_openai_parameters_are_still_forwarded(self):
        captured = {}

        async def upstream(**kwargs):
            captured.update(kwargs)
            return _FakeResponse()

        params = {
            "temperature": 0.2,
            "top_p": 0.9,
            "max_tokens": 64,
            "stop": ["\n"],
            "tools": [{"type": "function", "function": {"name": "f", "parameters": {}}}],
            "tool_choice": "auto",
            "response_format": {"type": "json_object"},
            "seed": 7,
            "user": "thread-user",
        }
        with patch.object(proxy_server, "preflight_input_estimate", return_value=(0.01, "test")), \
             patch.object(proxy_server.litellm, "acompletion", side_effect=upstream):
            response = self.client.post(
                "/v1/chat/completions",
                headers={"authorization": "Bearer sk-user"},
                json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}], **params},
            )
        self.assertEqual(response.status_code, 200)
        for key, value in params.items():
            self.assertEqual(captured[key], value)
        self.assertEqual(captured["api_key"], "sk-user")
        self.assertNotIn("api_base", captured)
        self.assertNotIn("base_url", captured)


# --- Bug 4: LiteLLM fetched a live price map from GitHub at import -----------


class Bug4PinnedLiteLLMPriceMapTests(unittest.TestCase):
    def test_importing_proxy_forces_litellm_local_price_map(self):
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in {"LITELLM_LOCAL_MODEL_COST_MAP"}
        }
        # If the remote fetch is attempted, make it fail fast instead of reaching
        # GitHub, so the test never depends on the network.
        for key in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
            env[key] = "http://127.0.0.1:9"
        env.pop("NO_PROXY", None)
        env.pop("no_proxy", None)
        code = (
            "import os, proxy_server\n"
            "from litellm.litellm_core_utils.get_model_cost_map import _cost_map_source_info as info\n"
            "print(os.environ.get('LITELLM_LOCAL_MODEL_COST_MAP'), info.is_env_forced, info.source)\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip().splitlines()[-1], "True True local")


# --- Bug 5: "I UNDERSTAND" unlock relocked on the next request ---------------


class Bug5AcknowledgmentLetsRequestsResumeTests(_IsolatedStateMixin, unittest.TestCase):
    budget = 1.0

    def _lock_over_threshold(self):
        state = config_manager.update_spend(1.05, thread_id="seed")
        self.assertTrue(state["is_locked"])

    def test_next_request_after_acknowledgment_is_admitted(self):
        self._lock_over_threshold()
        result = config_manager.unlock_circuit_breaker()

        reservation = config_manager.reserve_preflight_budget("after-ack", 0.01, thread_id="A")
        self.assertTrue(reservation["accepted"], reservation)
        self.assertFalse(config_manager.get_state()["is_locked"])
        state = config_manager.update_spend(0.02, thread_id="A", reservation_id="after-ack")
        self.assertFalse(state["is_locked"])
        self.assertEqual(result["effective_limit_usd"], 2.05)
        # The saved threshold is not changed by an acknowledgment.
        self.assertEqual(config_manager.get_config()["daily_budget_limit_usd"], 1.0)

    def test_routed_request_resumes_after_unlock_endpoint(self):
        self._lock_over_threshold()
        unlock = self.client.post("/api/unlock", headers=self._control_headers())
        self.assertEqual(unlock.status_code, 200)

        async def upstream(**kwargs):
            return _FakeResponse()

        with patch.object(proxy_server, "preflight_input_estimate", return_value=(0.01, "test")), \
             patch.object(proxy_server.litellm, "acompletion", side_effect=upstream):
            response = self.client.post(
                "/v1/chat/completions",
                headers={"authorization": "Bearer sk-test"},
                json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
            )
        self.assertEqual(response.status_code, 200, response.text)
        status = self.client.get("/api/status").json()
        self.assertEqual(status["pacing_threshold_usd"], 2.05)
        self.assertEqual(status["configured_threshold_usd"], 1.0)
        self.assertEqual(status["acknowledged_headroom_usd"], 1.05)

    def test_lock_reengages_at_new_effective_threshold(self):
        self._lock_over_threshold()
        config_manager.unlock_circuit_breaker()
        state = config_manager.update_spend(1.00, thread_id="A")
        self.assertTrue(state["is_locked"])

    def test_acknowledgment_headroom_resets_next_day(self):
        self._lock_over_threshold()
        config_manager.unlock_circuit_breaker()
        state = config_manager.get_state()
        state["date"] = str(date.today() - timedelta(days=1))
        config_manager.save_state(state)
        fresh = config_manager.get_state()
        self.assertEqual(fresh["acknowledged_headroom_usd"], 0.0)
        self.assertEqual(fresh["acknowledgment_count"], 0)
        self.assertEqual(config_manager.get_effective_limit(), 1.0)


# --- Bug 6: unpriced turns were posted as $0 ---------------------------------


class Bug6UnpricedTurnsAreNotFakeZeroTests(_IsolatedStateMixin, unittest.TestCase):
    def test_unpriced_turn_posts_preflight_estimate_and_is_flagged(self):
        reservation_id = "unpriced-turn"
        self.assertTrue(config_manager.reserve_preflight_budget(reservation_id, 0.03, thread_id="T")["accepted"])
        start = datetime.now()
        proxy_server.track_cost_callback(
            {
                "model": "other-provider/model",
                "response_cost": 0.0,
                "litellm_params": {
                    "litellm_metadata": {
                        proxy_server.THREAD_METADATA_KEY: "T",
                        proxy_server.RESERVATION_METADATA_KEY: reservation_id,
                    }
                },
            },
            {"model": "other-provider/model", "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6}},
            start,
            start + timedelta(milliseconds=10),
        )
        state = config_manager.get_state()
        self.assertEqual(state["current_spend_usd"], 0.03)
        self.assertEqual(state["unpriced_turn_count"], 1)
        self.assertEqual(state["unpriced_preflight_estimate_usd"], 0.03)
        self.assertEqual(config_manager.get_inflight_reserved_usd(), 0.0)

        record = turn_ledger.read_turns(thread_id="T")[0]
        self.assertIsNone(record["estimated_cost_usd"])
        self.assertEqual(record["cost_basis"], "unavailable")

        status = self.client.get("/api/status").json()
        self.assertEqual(status["unpriced_turn_count"], 1)
        self.assertEqual(status["unpriced_preflight_estimate_usd"], 0.03)

    def test_update_spend_with_none_is_not_posted_as_zero(self):
        self.assertTrue(config_manager.reserve_preflight_budget("r", 0.07, thread_id="T")["accepted"])
        state = config_manager.update_spend(None, thread_id="T", reservation_id="r")
        self.assertEqual(state["current_spend_usd"], 0.07)
        self.assertEqual(state["unpriced_turn_count"], 1)


# --- Bug 7: dashboard hard-coded port 8080 -----------------------------------


class Bug7DashboardShowsRealPortTests(_IsolatedStateMixin, unittest.TestCase):
    def test_dashboard_and_status_use_bound_port(self):
        client = TestClient(proxy_server.app, base_url="http://127.0.0.1:8085")
        html = client.get("/dashboard").text
        self.assertIn("http://127.0.0.1:8085/v1", html)
        self.assertNotIn("127.0.0.1:8080", html)
        self.assertNotIn("__TOKENTOTALS_PORT__", html)
        self.assertIn('id="latencyVal" style="font-size:22px;">8085 <span', html)

        status = client.get("/api/status").json()
        self.assertEqual(status["port"], 8085)
        self.assertEqual(status["configured_port"], 8080)


if __name__ == "__main__":
    unittest.main()
