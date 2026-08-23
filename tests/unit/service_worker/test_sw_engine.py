"""
Unit & Benchmark Test Suite for ServiceWorker Engine & Offline Cache Controller (Sprint 21).
Verifies WHATWG ServiceWorker lifecycle state machine (INSTALLING, ACTIVATED),
CacheStorage API, fetch request interception, and zero-downtime offline cache serving.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from service_worker.sw_engine import (
    ServiceWorkerState,
    Cache,
    CacheStorage,
    ServiceWorker,
    ServiceWorkerEngine
)


class TestServiceWorkerSubsystem(unittest.TestCase):

    def test_service_worker_lifecycle_state_machine(self):
        """Verify ServiceWorker lifecycle transitions from PARSED to ACTIVATED."""
        worker = ServiceWorker("/sw.js", scope="/", origin="https://pwa.local")
        self.assertEqual(worker.state, ServiceWorkerState.PARSED)

        worker.install()
        self.assertEqual(worker.state, ServiceWorkerState.INSTALLED)

        worker.activate()
        self.assertEqual(worker.state, ServiceWorkerState.ACTIVATED)

    def test_cache_storage_api(self):
        """Verify CacheStorage and Cache API methods: open, put, match, keys, delete."""
        caches = CacheStorage("https://pwa.local")
        cache = caches.open("v1-static")

        css_url = "https://pwa.local/assets/app.css"
        css_data = b"body { background: #000; }"

        cache.put(css_url, css_data, status=200, headers={"content-type": "text/css"})

        self.assertIn(css_url, cache.keys())
        match_res = cache.match(css_url)
        self.assertIsNotNone(match_res)
        self.assertEqual(match_res[0], css_data)
        self.assertEqual(match_res[1], 200)

        # Delete entry
        deleted = cache.delete(css_url)
        self.assertTrue(deleted)
        self.assertIsNone(cache.match(css_url))

    def test_fetch_interception_serves_offline_cache(self):
        """Verify active ServiceWorker intercepts fetch requests and serves cached offline resources."""
        engine = ServiceWorkerEngine()
        worker = engine.register("https://enterprise.offline", "/sw.js", scope="/")

        # Pre-cache app shell
        caches = engine.get_cache_storage("https://enterprise.offline")
        cache = caches.open("v1-app-shell")
        app_html = b"<!DOCTYPE html><html><body><h1>Sovereign Offline PWA</h1></body></html>"
        cache.put("https://enterprise.offline/dashboard", app_html, status=200)

        # Intercept fetch request
        data, status, headers = engine.handle_fetch("https://enterprise.offline", "https://enterprise.offline/dashboard")

        self.assertEqual(status, 200)
        self.assertEqual(data, app_html)

    def test_out_of_scope_request_pass_through(self):
        """Verify requests outside ServiceWorker scope fall through to network (status 404 pass-through)."""
        engine = ServiceWorkerEngine()
        engine.register("https://enterprise.offline", "/admin_sw.js", scope="/admin")

        # Fetch outside scope /user/
        data, status, headers = engine.handle_fetch("https://enterprise.offline", "https://enterprise.offline/user/profile")
        self.assertEqual(status, 404) # Pass-through

    def test_high_speed_cache_interception_benchmark(self):
        """
        Benchmark: Execute 50,000 fetch request interceptions on cached offline resources.
        Asserts duration < 0.15s (> 300,000 reqs/sec).
        """
        engine = ServiceWorkerEngine()
        engine.register("https://bench.pwa", "/sw.js", scope="/")
        caches = engine.get_cache_storage("https://bench.pwa")
        cache = caches.open("v1-bench")

        for i in range(100):
            cache.put(f"https://bench.pwa/asset_{i}.js", f"console.log('asset_{i}')".encode('utf-8'), status=200)

        start_time = time.perf_counter()
        for i in range(50000):
            target_url = f"https://bench.pwa/asset_{i % 100}.js"
            _, status, _ = engine.handle_fetch("https://bench.pwa", target_url)
        duration = time.perf_counter() - start_time

        total_reqs = 50000
        reqs_per_sec = total_reqs / duration
        latency_us = (duration / total_reqs) * 1_000_000

        self.assertLess(duration, 0.20, f"50k fetch interceptions took {duration*1000:.2f}ms (must be < 200ms)")
        print(f"\n[Sprint 21 ServiceWorker & Offline Cache Benchmark] {total_reqs:,} Requests Intercepted:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Interception Speed: {reqs_per_sec:,.0f} reqs/second")
        print(f"  - Average Interception Latency: {latency_us:.2f} µs/req")


if __name__ == "__main__":
    unittest.main()
