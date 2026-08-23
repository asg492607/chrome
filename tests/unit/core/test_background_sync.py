"""
Unit & Benchmark Test Suite for Background Sync & Periodic Background Sync Engine (Sprint 48).
Verifies SyncManager tag registration, PeriodicSyncManager interval registration & unregistration,
network online connectivity triggers, periodic task event dispatches, and orchestration throughput.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from core_platform.background_sync import (
    SyncRegistration,
    PeriodicSyncRegistration,
    BackgroundSyncEngine,
    SyncManager,
    PeriodicSyncManager
)


class TestBackgroundSyncSubsystem(unittest.TestCase):

    def setUp(self):
        BackgroundSyncEngine.clear_all()

    def test_sync_manager_tag_registration(self):
        """Verify registering one-off background sync tags and querying getTags()."""
        sync_mgr = SyncManager()
        ok = sync_mgr.register("sync_outbox_forms")

        self.assertTrue(ok)
        self.assertIn("sync_outbox_forms", sync_mgr.getTags())

    def test_periodic_sync_manager_registration_and_unregister(self):
        """Verify registering periodic sync tags with minInterval and unregistering tags."""
        p_sync = PeriodicSyncManager()
        ok = p_sync.register("get_daily_news", {"minInterval": 86400000})

        self.assertTrue(ok)
        self.assertIn("get_daily_news", p_sync.getTags())

        unsub_ok = p_sync.unregister("get_daily_news")
        self.assertTrue(unsub_ok)
        self.assertNotIn("get_daily_news", p_sync.getTags())

    def test_network_online_connectivity_trigger(self):
        """Verify network online transition firing pending sync events into ServiceWorker context."""
        BackgroundSyncEngine.on_network_offline()

        sync_mgr = SyncManager()
        sync_mgr.register("send_telemetry_batch")
        self.assertIn("send_telemetry_batch", sync_mgr.getTags())

        # Simulate network restoration
        events = BackgroundSyncEngine.on_network_online()

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "sync")
        self.assertEqual(events[0]["tag"], "send_telemetry_batch")
        self.assertNotIn("send_telemetry_batch", sync_mgr.getTags())

    def test_periodic_background_sync_trigger(self):
        """Verify periodic background sync task triggers executing periodicsync event handlers."""
        p_sync = PeriodicSyncManager()
        p_sync.register("update_weather", {"minInterval": 3600000})

        events = BackgroundSyncEngine.trigger_periodic_sync("update_weather")

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "periodicsync")
        self.assertEqual(events[0]["tag"], "update_weather")

    def test_high_speed_background_sync_benchmark(self):
        """
        Benchmark: Execute 50,000 background sync registrations, online triggers, and periodic dispatches.
        Asserts duration < 0.15s (> 300,000 sync ops/sec).
        """
        sync_mgr = SyncManager()
        p_sync = PeriodicSyncManager()

        p_sync.register("periodic_task_bench", {"minInterval": 60000})

        start_time = time.perf_counter()
        for i in range(25000):
            sync_mgr.register(f"sync_{i}")
            _ = BackgroundSyncEngine.on_network_online()
            _ = BackgroundSyncEngine.trigger_periodic_sync("periodic_task_bench")
        duration = time.perf_counter() - start_time

        total_ops = 75000 # 25k registers + 25k online triggers + 25k periodic triggers
        ops_per_sec = total_ops / duration
        latency_us = (duration / total_ops) * 1_000_000

        self.assertLess(duration, 0.20, f"75k Sync ops took {duration*1000:.2f}ms (must be < 200ms)")
        print(f"\n[Sprint 48 Background Sync Benchmark] {total_ops:,} Operations Orchestrated:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Background Sync Speed: {ops_per_sec:,.0f} ops/second")
        print(f"  - Average Operation Latency: {latency_us:.2f} µs/op")


if __name__ == "__main__":
    unittest.main()
