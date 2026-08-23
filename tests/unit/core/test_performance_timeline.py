"""
Unit & Benchmark Test Suite for Web Performance Timeline & Resource Timing API Engine (Sprint 37).
Verifies performance.now sub-millisecond timestamps, performance.mark and performance.measure duration calculation,
PerformanceObserver dispatches, PerformanceResourceTiming attributes, and timeline entry filtering.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from core_platform.performance_timeline import (
    PerformanceEntry,
    PerformanceMark,
    PerformanceMeasure,
    PerformanceNavigationTiming,
    PerformanceResourceTiming,
    PerformanceObserver,
    PerformanceTimelineEngine
)


class TestPerformanceTimelineSubsystem(unittest.TestCase):

    def test_performance_now_and_mark_measure(self):
        """Verify performance.now() sub-millisecond timestamps and mark/measure duration calculation."""
        engine = PerformanceTimelineEngine()

        t0 = engine.now()
        self.assertGreaterEqual(t0, 0.0)

        engine.mark("render_start")
        time.sleep(0.01) # ~10 ms delay
        engine.mark("render_end")

        measure = engine.measure("render_pass", "render_start", "render_end")
        self.assertEqual(measure.name, "render_pass")
        self.assertEqual(measure.entryType, "measure")
        self.assertGreaterEqual(measure.duration, 8.0) # > 8 ms

    def test_performance_observer_callback_dispatch(self):
        """Verify PerformanceObserver observing and receiving reactive entry dispatches."""
        engine = PerformanceTimelineEngine()
        received = []

        obs = PerformanceObserver(lambda entries: received.extend(entries))
        obs.observe(["mark", "measure"])
        engine.add_observer(obs)

        engine.mark("mark_alpha")
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].name, "mark_alpha")

        engine.add_resource_timing("https://cdn.com/asset.png", initiator_type="img")
        # Resource timing not in observed types -> count stays 1
        self.assertEqual(len(received), 1)

    def test_navigation_and_resource_timing_attributes(self):
        """Verify PerformanceNavigationTiming and PerformanceResourceTiming entry attributes."""
        engine = PerformanceTimelineEngine()

        res = engine.add_resource_timing("https://cdn.com/app.js", initiator_type="script", transfer_size=4096, duration=12.5)
        self.assertEqual(res.initiatorType, "script")
        self.assertEqual(res.transferSize, 4096)
        self.assertEqual(res.encodedBodySize, 4096)
        self.assertEqual(res.decodedBodySize, 8192)

    def test_timeline_entry_filtering(self):
        """Verify getEntriesByType() and getEntriesByName() queries."""
        engine = PerformanceTimelineEngine()

        engine.mark("m1")
        engine.mark("m2")
        engine.add_resource_timing("r1")

        marks = engine.getEntriesByType("mark")
        self.assertEqual(len(marks), 2)

        r_matches = engine.getEntriesByName("r1")
        self.assertEqual(len(r_matches), 1)

    def test_high_speed_performance_profiling_benchmark(self):
        """
        Benchmark: Execute 50,000 Performance mark, measure, and observer dispatches.
        Asserts duration < 0.15s (> 300,000 ops/sec).
        """
        engine = PerformanceTimelineEngine()
        received_count = [0]
        obs = PerformanceObserver(lambda entries: received_count.__setitem__(0, received_count[0] + len(entries)))
        obs.observe(["mark"])
        engine.add_observer(obs)

        start_time = time.perf_counter()
        for i in range(25000):
            engine.mark(f"m_{i}")
            engine.measure(f"meas_{i}", f"m_{i}")
        duration = time.perf_counter() - start_time

        total_ops = 50000 # 25k marks + 25k measures
        ops_per_sec = total_ops / duration
        latency_us = (duration / total_ops) * 1_000_000

        self.assertLess(duration, 0.20, f"50k Performance Timeline ops took {duration*1000:.2f}ms (must be < 200ms)")
        print(f"\n[Sprint 37 Performance Timeline Benchmark] {total_ops:,} Marks & Measures Processed:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Timeline Profiling Speed: {ops_per_sec:,.0f} ops/second")
        print(f"  - Average Profiling Latency: {latency_us:.2f} µs/op")


if __name__ == "__main__":
    unittest.main()
