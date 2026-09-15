import importlib
import unittest
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

import runtime_model_catalog


class RuntimeModelCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proxy = importlib.import_module("proxy_server")

    def _post_with_forbidden_upstream(self, payload):
        litellm_obj = self.proxy.litellm
        had_acompletion = hasattr(litellm_obj, "acompletion")
        original_acompletion = getattr(litellm_obj, "acompletion", None)
        litellm_obj.acompletion = AsyncMock(
            side_effect=AssertionError("upstream must not be called")
        )
        try:
            client = TestClient(self.proxy.app)
            return client.post("/v1/chat/completions", json=payload)
        finally:
            if had_acompletion:
                litellm_obj.acompletion = original_acompletion
            else:
                delattr(litellm_obj, "acompletion")

    def test_catalog_matches_canonical_registry_keys(self):
        expected = []
        for provider, loader in runtime_model_catalog._PROVIDER_LOADERS:
            registry = loader()
            verified_at = registry.get("verified_at")
            for model_id, record in (registry.get("models") or {}).items():
                expected.append(
                    {
                        "id": model_id,
                        "object": "model",
                        "owned_by": provider,
                        "tokentotals_pricing_registry": True,
                        "tokentotals_verified_at": verified_at,
                        "tokentotals_limited_availability": bool(
                            isinstance(record, dict)
                            and record.get("limited_availability", False)
                        ),
                    }
                )

        expected = sorted(expected, key=lambda item: (item["owned_by"], item["id"]))
        actual = runtime_model_catalog.registered_model_entries()
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), len({item["id"] for item in actual}))

    def test_aliases_are_not_advertised_as_separate_canonical_models(self):
        advertised = set(runtime_model_catalog.registered_model_ids())
        for _provider, loader in runtime_model_catalog._PROVIDER_LOADERS:
            registry = loader()
            canonical = set((registry.get("models") or {}).keys())
            for record in (registry.get("models") or {}).values():
                if not isinstance(record, dict):
                    continue
                for alias in record.get("aliases") or []:
                    if alias not in canonical:
                        self.assertNotIn(alias, advertised)

    def test_endpoint_matches_registry_catalog_exactly(self):
        client = TestClient(self.proxy.app)
        response = client.get("/v1/models")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["object"], "list")
        self.assertEqual(
            payload["data"],
            runtime_model_catalog.registered_model_entries(),
        )

    def test_catalog_metadata_identifies_registry_scope_not_entitlement(self):
        entries = runtime_model_catalog.registered_model_entries()
        self.assertTrue(entries)
        self.assertEqual(
            {entry["owned_by"] for entry in entries},
            {"openai", "anthropic", "google"},
        )
        for entry in entries:
            self.assertTrue(entry["tokentotals_pricing_registry"])
            self.assertTrue(entry["tokentotals_verified_at"])
            self.assertIsInstance(entry["tokentotals_limited_availability"], bool)

    def test_missing_model_is_rejected_before_upstream_call(self):
        response = self._post_with_forbidden_upstream(
            {"messages": [{"role": "user", "content": "hello"}]}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("explicit non-empty model ID", response.json()["detail"])

    def test_blank_model_is_rejected_before_upstream_call(self):
        response = self._post_with_forbidden_upstream(
            {
                "model": "   ",
                "messages": [{"role": "user", "content": "hello"}],
            }
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("explicit non-empty model ID", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
