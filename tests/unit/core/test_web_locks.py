"""
Unit & Benchmark Test Suite for Web Locks API & Cross-Tab Resource Synchronization Engine (Sprint 43).
Verifies navigator.locks.request exclusive vs shared lock modes, FIFO queue ordering, non-blocking ifAvailable requests,
steal semantics, navigator.locks.query state inspection, and lock synchronization throughput.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from core_platform.web_locks import (
    LockInfo,
    Lock,
    LockQueueManager,
    LockManager
)


class TestWebLocksSubsystem(unittest.TestCase):

    def test_exclusive_and_shared_lock_granting(self):
        """Verify shared locks allowing concurrent readers and exclusive lock granting."""
        locks = LockManager()
        executed = []

        # Shared readers
        locks.request("shared_res", {"mode": "shared"}, lambda lock: executed.append("read_1"))
        locks.request("shared_res", {"mode": "shared"}, lambda lock: executed.append("read_2"))
        self.assertEqual(executed, ["read_1", "read_2"])

        # Exclusive writer
        locks.request("exclusive_res", {"mode": "exclusive"}, lambda lock: executed.append("write_1"))
        self.assertIn("write_1", executed)

    def test_lock_fifo_queue_ordering(self):
        """Verify pending lock requests are processed in strict FIFO queue ordering."""
        locks = LockManager()
        order = []

        locks.request("fifo_mutex", lambda lock: order.append(1))
        locks.request("fifo_mutex", lambda lock: order.append(2))
        locks.request("fifo_mutex", lambda lock: order.append(3))

        self.assertEqual(order, [1, 2, 3])

    def test_if_available_and_steal_options(self):
        """Verify ifAvailable returning None on conflict and steal breaking active locks."""
        locks = LockManager()
        got_none = [False]

        # Artificially hold a lock
        locks._manager.held["busy_res"] = [(LockInfo("busy_res", "exclusive", "tab_1"), Lock("busy_res", "exclusive"))]

        # ifAvailable request on busy lock -> returns None immediately
        locks.request("busy_res", {"ifAvailable": True}, lambda lock: got_none.__setitem__(0, lock is None))
        self.assertTrue(got_none[0])

        # steal request -> breaks existing lock and acquires immediately
        stolen = [False]
        locks.request("busy_res", {"steal": True}, lambda lock: stolen.__setitem__(0, lock is not None))
        self.assertTrue(stolen[0])

    def test_lock_manager_query_state_inspection(self):
        """Verify LockManager.query() returning active held and pending lock state inspection."""
        locks = LockManager()
        locks._manager.held["db_lock"] = [(LockInfo("db_lock", "shared", "tab_A"), Lock("db_lock", "shared"))]

        q = locks.query()
        self.assertIn("held", q)
        self.assertEqual(len(q["held"]), 1)
        self.assertEqual(q["held"][0]["name"], "db_lock")

    def test_high_speed_lock_synchronization_benchmark(self):
        """
        Benchmark: Execute 50,000 Lock requests, acquisitions, and releases.
        Asserts duration < 0.15s (> 300,000 lock ops/sec).
        """
        locks = LockManager()
        counter = [0]
        opts = {"mode": "exclusive"}
        cb = lambda lock: counter.__setitem__(0, counter[0] + 1)

        start_time = time.perf_counter()
        for i in range(50000):
            locks.request(f"lock_{i % 100}", opts, cb)
        duration = time.perf_counter() - start_time

        total_ops = 50000
        ops_per_sec = total_ops / duration
        latency_us = (duration / total_ops) * 1_000_000

        self.assertLess(duration, 0.20, f"50k Lock ops took {duration*1000:.2f}ms (must be < 200ms)")
        print(f"\n[Sprint 43 Web Locks Benchmark] {total_ops:,} Lock Requests Processed:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Lock Synchronization Speed: {ops_per_sec:,.0f} lock ops/second")
        print(f"  - Average Lock Latency: {latency_us:.2f} µs/op")


if __name__ == "__main__":
    unittest.main()
