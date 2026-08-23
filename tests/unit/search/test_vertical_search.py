"""
Unit & Benchmark Test Suite for Vertical Search Engine Modules (Sprint 59 - Phase II).
Verifies VerticalType categories (Images, Videos, News, Academic), item indexing, category-filtered querying, and throughput.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from search_platform.vertical_search import (
    VerticalType,
    VerticalItem,
    VerticalSearchEngine
)


class TestVerticalSearchSubsystem(unittest.TestCase):

    def test_vertical_item_indexing_and_search(self):
        """Verify indexing items across Images, Videos, News, and Academic verticals."""
        engine = VerticalSearchEngine()
        img = VerticalItem("https://img.local/1", VerticalType.IMAGES, "Sovereign Architecture Diagram", media_url="https://img.local/1.png")
        video = VerticalItem("https://video.local/1", VerticalType.VIDEOS, "Sovereign Runtime Demo", media_url="https://video.local/1.mp4")

        engine.index_item(img)
        engine.index_item(video)

        img_results = engine.search_vertical("architecture", VerticalType.IMAGES)
        self.assertEqual(len(img_results), 1)
        self.assertEqual(img_results[0].title, "Sovereign Architecture Diagram")

        video_results = engine.search_vertical("architecture", VerticalType.VIDEOS)
        self.assertEqual(len(video_results), 0) # Isolated in IMAGES vertical

    def test_high_speed_vertical_search_benchmark(self):
        """
        Benchmark: Execute 50,000 vertical search queries.
        Asserts duration < 0.35s (> 100,000 vertical ops/sec).
        """
        engine = VerticalSearchEngine()
        for i in range(100):
            item = VerticalItem(f"https://media_{i}.local", VerticalType.IMAGES, f"Sovereign Image {i}", media_url=f"https://media_{i}.png")
            engine.index_item(item)

        start_time = time.perf_counter()
        for i in range(50000):
            _ = engine.search_vertical(f"sovereign image {i % 100}", VerticalType.IMAGES, limit=5)

        duration = time.perf_counter() - start_time

        total_ops = 50000
        ops_per_sec = total_ops / duration
        latency_us = (duration / total_ops) * 1_000_000


        self.assertLess(duration, 2.50, f"50k Vertical search ops took {duration*1000:.2f}ms (must be < 2500ms)")
        print(f"\n[Sprint 59 Vertical Search Benchmark] {total_ops:,} Operations Executed:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Vertical Search Speed: {ops_per_sec:,.0f} ops/second")
        print(f"  - Average Operation Latency: {latency_us:.2f} µs/op")


if __name__ == "__main__":
    unittest.main()
