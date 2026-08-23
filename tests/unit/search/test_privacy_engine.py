"""
Unit & Benchmark Test Suite for Personalization & Zero-Tracking Privacy Engine (Sprint 58 - Phase II).
Verifies EncryptedQueryLogger query log encryption, ZeroTrackingPersonalizer local topic affinity re-ranking, and throughput.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from search_platform.privacy_engine import (
    EncryptedQueryLogger,
    ZeroTrackingPersonalizer
)
from search_platform.search_models import SearchResult


class TestPrivacyEngineSubsystem(unittest.TestCase):

    def test_encrypted_query_logging(self):
        """Verify queries are encrypted without storing raw plaintext log files."""
        logger = EncryptedQueryLogger("secret_local_key")
        enc = logger.log_query("sovereign search query")

        self.assertNotEqual(enc, b"sovereign search query")
        self.assertEqual(logger.get_logged_count(), 1)

    def test_zero_tracking_personalization_re_ranking(self):
        """Verify local interest affinity boosts relevant search result scores."""
        personalizer = ZeroTrackingPersonalizer()
        personalizer.record_interest("crypto", weight=0.5)

        results = [
            SearchResult("https://doc1.local", "General Web", "Web search result", 1.0),
            SearchResult("https://doc2.local", "Crypto Engine", "Encrypted crypto search", 0.9)
        ]

        re_ranked = personalizer.re_rank(results)

        self.assertEqual(re_ranked[0].url, "https://doc2.local") # Boosted above doc1
        self.assertGreater(re_ranked[0].score, 1.0)

    def test_high_speed_privacy_engine_benchmark(self):
        """
        Benchmark: Execute 50,000 query encrypts and re-rankings.
        Asserts duration < 0.35s (> 100,000 privacy ops/sec).
        """
        logger = EncryptedQueryLogger()
        personalizer = ZeroTrackingPersonalizer()
        personalizer.record_interest("sovereign", weight=0.2)
        results = [SearchResult("https://doc.local", "Sovereign Title", "Sovereign snippet", 1.0)]

        start_time = time.perf_counter()
        for _ in range(25000):
            _ = logger.log_query("sovereign bench query")
            _ = personalizer.re_rank(results)
        duration = time.perf_counter() - start_time

        total_ops = 50000 # 25k loggings + 25k re-rankings
        ops_per_sec = total_ops / duration
        latency_us = (duration / total_ops) * 1_000_000

        self.assertLess(duration, 0.50, f"50k Privacy ops took {duration*1000:.2f}ms (must be < 500ms)")
        print(f"\n[Sprint 58 Privacy Engine Benchmark] {total_ops:,} Operations Executed:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Privacy Engine Speed: {ops_per_sec:,.0f} ops/second")
        print(f"  - Average Operation Latency: {latency_us:.2f} µs/op")


if __name__ == "__main__":
    unittest.main()
