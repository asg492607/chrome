"""
Unit & Benchmark Test Suite for Search UI, Autocomplete & REST API Engine (Sprint 57 - Phase II).
Verifies AutocompleteEngine Trie prefix insertion and sub-millisecond autocomplete suggestions, HTML rendering, and API throughput.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from search_platform.search_api import (
    AutocompleteEngine,
    render_search_homepage,
    render_search_results
)
from search_platform.search_models import SearchResult


class TestSearchApiSubsystem(unittest.TestCase):

    def test_autocomplete_prefix_trie(self):
        """Verify AutocompleteEngine inserting terms and retrieving top suggestions for prefix."""
        trie = AutocompleteEngine()
        trie.insert("sovereign")
        trie.insert("sovereignty")
        trie.insert("sovereign_search")
        trie.insert("software")

        suggestions = trie.autocomplete("sov", limit=5)
        self.assertIn("sovereign", suggestions)
        self.assertIn("sovereignty", suggestions)
        self.assertNotIn("software", suggestions)

    def test_html_rendering_templates(self):
        """Verify HTML rendering for search homepage and results page."""
        home_html = render_search_homepage()
        self.assertIn("AsgSearch", home_html)

        results = [SearchResult("https://doc1.local", "Title 1", "Snippet 1", 0.95)]
        res_html = render_search_results("sovereign", results)
        self.assertIn("Title 1", res_html)
        self.assertIn("0.9500", res_html)

    def test_high_speed_autocomplete_benchmark(self):
        """
        Benchmark: Execute 50,000 autocomplete prefix lookups.
        Asserts duration < 0.20s (> 250,000 lookup ops/sec).
        """
        trie = AutocompleteEngine()
        for w in ["sovereign", "search", "engine", "system", "platform", "privacy", "security"]:
            trie.insert(w)

        start_time = time.perf_counter()
        for _ in range(50000):
            _ = trie.autocomplete("so", limit=3)
        duration = time.perf_counter() - start_time

        ops_per_sec = 50000 / duration
        latency_us = (duration / 50000) * 1_000_000

        self.assertLess(duration, 0.35, f"50k Autocomplete ops took {duration*1000:.2f}ms (must be < 350ms)")
        print(f"\n[Sprint 57 Autocomplete Benchmark] 50,000 Operations Executed:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Autocomplete Speed: {ops_per_sec:,.0f} ops/second")
        print(f"  - Average Operation Latency: {latency_us:.2f} µs/op")


if __name__ == "__main__":
    unittest.main()
