"""Deterministic resource limits and result lifecycle; no real inputs."""
import unittest
from dataclasses import replace

from workflow_doctor.api.config import ApiConfig
from workflow_doctor.api.models import ApiProblem
from workflow_doctor.api.store import ResultStore


class StoreTests(unittest.TestCase):
    def test_reject_nonpositive_limits_and_nonlocal_cors(self):
        for field in ("max_results", "max_request_bytes", "result_ttl_seconds", "max_response_bytes"):
            with self.assertRaises(ValueError):
                ApiConfig(**{field: 0})
        with self.assertRaises(ValueError):
            ApiConfig(cors_origins=("*",))
        with self.assertRaises(ValueError):
            ApiConfig(max_result_bytes=2, max_cache_bytes=1)

    def test_result_limit_rejects_without_caching(self):
        store = ResultStore(ApiConfig(max_result_bytes=1))
        with self.assertRaises(ApiProblem) as exc:
            store.put({"value": "synthetic"})
        self.assertEqual(exc.exception.code, "RESULT_TOO_LARGE")
        self.assertEqual(store._bytes, 0)

    def test_count_limit_evicts_oldest_without_touch_refresh(self):
        store = ResultStore(ApiConfig(max_results=1))
        first = store.put({"value": 1})
        second = store.put({"value": 2})
        with self.assertRaises(ApiProblem):
            store.get(first.scan_id)
        self.assertEqual(store.get(second.scan_id).report(), {"value": 2})

    def test_byte_limit_is_enforced_across_results(self):
        store = ResultStore(ApiConfig(max_result_bytes=15, max_cache_bytes=20))
        first = store.put({"value": 1})
        second = store.put({"value": 2})
        self.assertLessEqual(store._bytes, 20)
        with self.assertRaises(ApiProblem):
            store.get(first.scan_id)
        self.assertEqual(store.get(second.scan_id).report(), {"value": 2})

    def test_ttl_purge_and_restart_do_not_restore_tasks(self):
        now = [0.0]
        store = ResultStore(ApiConfig(result_ttl_seconds=1), clock=lambda: now[0])
        item = store.put({"value": 1})
        now[0] = 1.0
        with self.assertRaises(ApiProblem):
            store.get(item.scan_id)
        self.assertEqual(store._bytes, 0)
        with self.assertRaises(ApiProblem):
            ResultStore(ApiConfig()).get(item.scan_id)

    def test_cache_is_an_immutable_snapshot_and_clear_drops_bytes(self):
        store = ResultStore(ApiConfig())
        original = {"value": 1}
        item = store.put(original)
        original["value"] = 2
        restored = item.report()
        restored["value"] = 3
        self.assertEqual(item.report(), {"value": 1})
        store.clear()
        self.assertEqual(store._bytes, 0)
        with self.assertRaises(ApiProblem):
            store.get(item.scan_id)
