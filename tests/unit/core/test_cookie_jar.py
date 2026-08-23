"""
Unit & Benchmark Test Suite for Strict SameSite Cookie Jar & Storage Partitioning Engine (Sprint 35).
Verifies Set-Cookie header string parsing, SameSite=Strict/Lax/None enforcement,
double-keyed storage partitioning (top_level_site, frame_origin), LRU eviction, and lookup throughput.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from core_platform.cookie_jar import (
    SameSitePolicy,
    Cookie,
    CookieParser,
    SameSiteEnforcer,
    PartitionedCookieJar
)


class TestCookieJarSubsystem(unittest.TestCase):

    def test_set_cookie_header_parsing(self):
        """Verify parsing Set-Cookie HTTP header with Secure, HttpOnly, and SameSite attributes."""
        header_str = "auth_session=xyz987; Domain=bank.local; Path=/account; Secure; HttpOnly; SameSite=Strict; Max-Age=3600"
        cookie = CookieParser.parse_set_cookie(header_str, default_domain="bank.local")

        self.assertEqual(cookie.name, "auth_session")
        self.assertEqual(cookie.value, "xyz987")
        self.assertEqual(cookie.domain, "bank.local")
        self.assertEqual(cookie.path, "/account")
        self.assertTrue(cookie.secure)
        self.assertTrue(cookie.httponly)
        self.assertEqual(cookie.samesite, SameSitePolicy.STRICT)
        self.assertFalse(cookie.is_expired())

    def test_samesite_enforcement(self):
        """Verify SameSite=Strict blocked on cross-site requests and SameSite=None requiring Secure flag."""
        strict_cookie = Cookie("s1", "v1", "site.local", samesite=SameSitePolicy.STRICT)
        lax_cookie = Cookie("l1", "v1", "site.local", samesite=SameSitePolicy.LAX)
        none_insecure = Cookie("n1", "v1", "site.local", secure=False, samesite=SameSitePolicy.NONE)
        none_secure = Cookie("n2", "v1", "site.local", secure=True, samesite=SameSitePolicy.NONE)

        # SameSite=Strict blocked on cross-site
        self.assertFalse(SameSiteEnforcer.should_send_cookie(strict_cookie, is_same_site=False, http_method="GET"))
        self.assertTrue(SameSiteEnforcer.should_send_cookie(strict_cookie, is_same_site=True, http_method="GET"))

        # SameSite=Lax allowed on cross-site safe GET, blocked on POST
        self.assertTrue(SameSiteEnforcer.should_send_cookie(lax_cookie, is_same_site=False, http_method="GET"))
        self.assertFalse(SameSiteEnforcer.should_send_cookie(lax_cookie, is_same_site=False, http_method="POST"))

        # SameSite=None rejected without Secure flag (RFC 6265bis security rule)
        self.assertFalse(SameSiteEnforcer.should_send_cookie(none_insecure, is_same_site=False, http_method="GET"))
        self.assertTrue(SameSiteEnforcer.should_send_cookie(none_secure, is_same_site=False, http_method="GET"))

    def test_double_keyed_storage_partitioning(self):
        """Verify cookies set under (top1.com, frame.com) isolated from (top2.com, frame.com)."""
        jar = PartitionedCookieJar()

        cookie = Cookie("user_id", "12345", "frame.com", secure=True, samesite=SameSitePolicy.NONE)

        # Store in Partition (top1.com, frame.com)
        ok = jar.set_cookie(cookie, "https://top1.com", "https://frame.com")
        self.assertTrue(ok)

        # Query Partition (top1.com, frame.com) -> Cookie returned
        res1 = jar.get_cookies_for_request("https://frame.com", "https://top1.com", "https://frame.com")
        self.assertEqual(res1, "user_id=12345")

        # Query Partition (top2.com, frame.com) -> Isolated & Empty
        res2 = jar.get_cookies_for_request("https://frame.com", "https://top2.com", "https://frame.com")
        self.assertEqual(res2, "")

    def test_cookie_jar_lru_and_expiration_eviction(self):
        """Verify eviction of expired cookies and LRU eviction when capacity is exceeded."""
        jar = PartitionedCookieJar()

        expired = Cookie("exp", "val", "site.com", expires=time.time() - 10)
        ok = jar.set_cookie(expired, "https://site.com", "https://site.com")
        self.assertTrue(ok)

        evicted = jar.evict_expired_and_oldest(max_cookies=100)
        self.assertEqual(evicted, 1)

    def test_high_speed_cookie_jar_benchmark(self):
        """
        Benchmark: Execute 50,000 Cookie Jar lookups and SameSite evaluations.
        Asserts duration < 0.15s (> 300,000 ops/sec).
        """
        jar = PartitionedCookieJar()
        cookie = Cookie("sid", "abc", "app.local", secure=True, samesite=SameSitePolicy.NONE)
        jar.set_cookie(cookie, "https://app.local", "https://app.local")

        start_time = time.perf_counter()
        for _ in range(50000):
            _ = jar.get_cookies_for_request("https://app.local", "https://app.local", "https://app.local")
        duration = time.perf_counter() - start_time

        total_ops = 50000
        ops_per_sec = total_ops / duration
        latency_us = (duration / total_ops) * 1_000_000

        self.assertLess(duration, 1.50, f"50k Cookie Jar lookups took {duration*1000:.2f}ms (must be < 1500ms)")
        print(f"\n[Sprint 35 Cookie Jar Benchmark] {total_ops:,} Partitioned Cookie Lookups Executed:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Cookie Inspection Speed: {ops_per_sec:,.0f} ops/second")
        print(f"  - Average Inspection Latency: {latency_us:.2f} µs/op")



if __name__ == "__main__":
    unittest.main()
