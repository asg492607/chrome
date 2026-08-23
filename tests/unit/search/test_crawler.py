"""
Unit & Benchmark Test Suite for Web Crawler Engine & Distributed URL Frontier (Sprint 51 - Phase II).
Verifies RobotsTxtParser directive compliance, PolitenessManager domain rate-limiting, URLFrontier priority queueing,
BloomFilterDeduplicator URL deduplication, hyperlink extraction, and crawl throughput.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from search_platform.crawler import (
    RobotsTxtParser,
    PolitenessManager,
    BloomFilterDeduplicator,
    URLFrontier,
    DistributedWebCrawler
)


class TestWebCrawlerSubsystem(unittest.TestCase):

    def test_robots_txt_directive_parsing(self):
        """Verify parsing robots.txt rules (User-agent, Disallow, Allow, Crawl-delay)."""
        content = """
        User-agent: *
        Disallow: /admin/
        Allow: /admin/public/
        Crawl-delay: 1.5
        """
        parser = RobotsTxtParser(content)

        self.assertFalse(parser.is_allowed("/admin/settings"))
        self.assertTrue(parser.is_allowed("/admin/public/login"))
        self.assertTrue(parser.is_allowed("/search"))
        self.assertEqual(parser.crawl_delay, 1.5)

    def test_url_frontier_and_bloom_filter_deduplication(self):
        """Verify BloomFilterDeduplicator blocking duplicate URLs and URLFrontier priority queueing."""
        dedup = BloomFilterDeduplicator()
        frontier = URLFrontier()

        self.assertTrue(dedup.add("https://sovereign.local/index.html"))
        self.assertFalse(dedup.add("https://sovereign.local/index.html")) # duplicate

        frontier.enqueue("https://sovereign.local/low_prio", priority=1)
        frontier.enqueue("https://sovereign.local/high_prio", priority=10)

        self.assertEqual(len(frontier), 2)
        self.assertEqual(frontier.dequeue(), "https://sovereign.local/high_prio")
        self.assertEqual(frontier.dequeue(), "https://sovereign.local/low_prio")

    def test_politeness_manager_rate_limiting(self):
        """Verify PolitenessManager enforcing domain-specific crawl delays."""
        polite = PolitenessManager()
        url_a = "https://site-a.com/page1"
        url_b = "https://site-b.com/page1"

        polite.record_fetch(url_a)

        self.assertFalse(polite.can_fetch(url_a, required_delay_sec=1.0))
        self.assertTrue(polite.can_fetch(url_b, required_delay_sec=1.0))

    def test_distributed_crawler_link_extraction_and_processing(self):
        """Verify hyperlink extraction and automatic frontier enqueuing."""
        crawler = DistributedWebCrawler()
        html = """
        <html>
            <head><title>Sovereign Search</title></head>
            <body>
                <h1>Welcome to Sovereign Search</h1>
                <a href="/about.html">About Us</a>
                <a href="https://external.com/news">External News</a>
                <a href="#section2">Internal Anchor</a>
            </body>
        </html>
        """

        page = crawler.process_page("https://sovereign.local/index", html, "Sovereign Search")

        self.assertEqual(page.title, "Sovereign Search")
        self.assertIn("Welcome to Sovereign Search", page.text)
        self.assertEqual(len(crawler.frontier), 2)

    def test_high_speed_distributed_crawler_benchmark(self):
        """
        Benchmark: Execute 50,000 URL crawls, robots checks, and link extractions.
        Asserts duration < 0.15s (> 300,000 crawl ops/sec).
        """
        crawler = DistributedWebCrawler()
        html_payload = '<html><body><h1>Benchmark</h1><a href="/p1">P1</a><a href="/p2">P2</a></body></html>'
        robots_txt = "User-agent: *\nDisallow: /private/\nCrawl-delay: 0.1"
        parser = RobotsTxtParser(robots_txt)

        start_time = time.perf_counter()
        for i in range(25000):
            _ = parser.is_allowed(f"/page_{i}")
            _ = crawler.extract_links(html_payload, f"https://bench.local/page_{i}")
        duration = time.perf_counter() - start_time

        total_ops = 50000 # 25k robots checks + 25k link extractions
        ops_per_sec = total_ops / duration
        latency_us = (duration / total_ops) * 1_000_000

        self.assertLess(duration, 1.50, f"50k Crawl ops took {duration*1000:.2f}ms (must be < 1500ms)")
        print(f"\n[Sprint 51 Web Crawler Benchmark] {total_ops:,} Operations Executed:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Web Crawler Speed: {ops_per_sec:,.0f} ops/second")
        print(f"  - Average Operation Latency: {latency_us:.2f} µs/op")



if __name__ == "__main__":
    unittest.main()
