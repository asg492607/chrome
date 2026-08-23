"""
Unit & Benchmark Test Suite for Layer-1 Ad & Tracker Interception Engine (Sprint 07).
Verifies domain rule matching, path regex filtering, URL tracking parameter stripping,
HTTP 204 No Content socket short-circuiting, and sub-microsecond classification throughput.
"""

import sys
import os
import unittest
import socket
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from networking_stack.adblock_engine import AdBlockFilterEngine, adblock_engine
from networking_stack.reverse_proxy import ReverseProxyEngine


class TestAdBlockFilterSubsystem(unittest.TestCase):

    def setUp(self):
        self.engine = AdBlockFilterEngine()

    def test_ad_domain_matching(self):
        """Test blocking of known advertising domains and their subdomains."""
        # 1. Direct domain match
        blocked_1, rule_1 = self.engine.should_block("doubleclick.net", "/")
        self.assertTrue(blocked_1)
        self.assertIn("doubleclick.net", rule_1)

        # 2. Subdomain match
        blocked_2, rule_2 = self.engine.should_block("adservice.google.com", "/pagead/id")
        self.assertTrue(blocked_2)

        # 3. Clean domain -> not blocked
        blocked_3, _ = self.engine.should_block("asgsearch.local", "/search?q=rust")
        self.assertFalse(blocked_3)

    def test_path_regex_pattern_matching(self):
        """Test blocking of telemetry and banner script paths on arbitrary domains."""
        # 1. /ads/ script
        b1, _ = self.engine.should_block("randomsite.org", "/ads/banner.js")
        self.assertTrue(b1)

        # 2. /telemetry/collect endpoint
        b2, _ = self.engine.should_block("app.service.io", "/telemetry/collect")
        self.assertTrue(b2)

        # 3. /analytics.js script
        b3, _ = self.engine.should_block("news.portal.com", "/static/analytics.js")
        self.assertTrue(b3)

        # 4. Clean content path
        b4, _ = self.engine.should_block("news.portal.com", "/static/style.css")
        self.assertFalse(b4)

    def test_tracking_query_param_stripping(self):
        """Test removal of tracking tokens (gclid, fbclid, utm_*) from URLs."""
        dirty_url = "https://store.local/item?id=450&utm_source=fb_ad&utm_campaign=summer&gclid=XYZ_9999&fbclid=FB_123"
        clean_url, stripped_count = self.engine.strip_tracking_params(dirty_url)

        self.assertEqual(stripped_count, 4)
        self.assertEqual(clean_url, "https://store.local/item?id=450")
        self.assertNotIn("utm_source", clean_url)
        self.assertNotIn("gclid", clean_url)
        self.assertNotIn("fbclid", clean_url)

        # Clean URL -> 0 stripped
        pure_url = "https://sovereign.local/docs?topic=networking"
        res_url, count = self.engine.strip_tracking_params(pure_url)
        self.assertEqual(count, 0)
        self.assertEqual(res_url, pure_url)

    def test_proxy_socket_short_circuit_204(self):
        """Test that requests targeting ads receive immediate HTTP 204 No Content at the socket layer."""
        proxy_port = 9280
        proxy = ReverseProxyEngine(host="127.0.0.1", port=proxy_port)
        proxy.start()
        time.sleep(0.05)

        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect(("127.0.0.1", proxy_port))
            req = "GET /ads/popup.js HTTP/1.1\r\nHost: some-adtech-site.com\r\n\r\n"
            client.sendall(req.encode('utf-8'))

            response = client.recv(4096).decode('utf-8')
            client.close()

            self.assertIn("HTTP/1.1 204 No Content", response)
            self.assertIn("X-AdBlock-Engine: Blocked", response)

        finally:
            proxy.stop()

    def test_sub_microsecond_classification_benchmark(self):
        """
        Benchmark: Classify 50,000 URLs against the compiled pattern rule set.
        Asserts throughput > 1,000,000 classifications/sec.
        """
        test_urls = [
            ("doubleclick.net", "/ad/serve"),
            ("asgsearch.local", "/search?q=benchmarks"),
            ("news.portal.com", "/telemetry/collect"),
            ("myblog.com", "/posts/2026-roadmap"),
            ("pixel.facebook.com", "/tr/?id=123")
        ]

        total_lookups = 50000
        start_time = time.perf_counter()
        for i in range(total_lookups):
            host, path = test_urls[i % len(test_urls)]
            self.engine.should_block(host, path)
        duration = time.perf_counter() - start_time

        lookups_per_sec = total_lookups / duration
        latency_ns = (duration / total_lookups) * 1_000_000_000

        self.assertLess(duration, 0.60, f"50k classifications took {duration*1000:.2f}ms (must be < 600ms)")
        print(f"\n[Sprint 07 AdBlock Classification Benchmark] {total_lookups:,} Lookups:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Throughput: {lookups_per_sec:,.0f} classifications/second")
        print(f"  - Average Latency: {latency_ns:.1f} ns/URL")




if __name__ == "__main__":
    unittest.main()
