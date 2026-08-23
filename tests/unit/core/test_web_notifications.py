"""
Unit & Benchmark Test Suite for Web Notifications & System Desktop Alert Dispatch Engine (Sprint 45).
Verifies Notification constructor options, Notification.requestPermission state machine, tag collapsing/deduplication,
action button click routing, close lifecycle, and notification dispatch throughput.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from core_platform.web_notifications import (
    DesktopNotificationCenter,
    Notification
)


class TestWebNotificationsSubsystem(unittest.TestCase):

    def setUp(self):
        DesktopNotificationCenter.clear_all()

    def test_notification_constructor_and_permission_lifecycle(self):
        """Verify creating Notification instance and requestPermission() state machine."""
        perm_result = []
        res = Notification.requestPermission(lambda perm: perm_result.append(perm))

        self.assertEqual(res, "granted")
        self.assertEqual(perm_result, ["granted"])

        show_called = [False]
        n = Notification("Security Alert", {"body": "Unauthorized IPC trapped by sandbox"})
        n.onshow = lambda: show_called.__setitem__(0, True)

        self.assertEqual(n.title, "Security Alert")
        self.assertEqual(n.body, "Unauthorized IPC trapped by sandbox")
        self.assertIn(n, DesktopNotificationCenter.get_active_notifications())

    def test_notification_tag_collapsing_and_deduplication(self):
        """Verify new notification with existing tag replacing previous notification."""
        n1 = Notification("Chat from Alice", {"tag": "chat_alice", "body": "Hello there!"})
        self.assertEqual(len(DesktopNotificationCenter.get_active_notifications()), 1)

        n2 = Notification("Chat from Alice", {"tag": "chat_alice", "body": "Are you available?"})

        # n1 should be closed and replaced by n2
        self.assertTrue(n1.closed)
        self.assertFalse(n2.closed)
        self.assertEqual(len(DesktopNotificationCenter.get_active_notifications()), 1)
        self.assertIn(n2, DesktopNotificationCenter.get_active_notifications())

    def test_notification_action_button_routing_and_click_events(self):
        """Verify triggering onclick and custom action click handlers."""
        actions = [{"action": "approve", "title": "Approve Request"}, {"action": "deny", "title": "Deny"}]
        n = Notification("Authorization Pending", {"actions": actions})

        clicked_evt = {}
        n.onclick = lambda evt: clicked_evt.update(evt)

        DesktopNotificationCenter.dispatch_action(n, "approve")

        self.assertEqual(clicked_evt.get("type"), "click")
        self.assertEqual(clicked_evt.get("action"), "approve")

    def test_notification_close_lifecycle(self):
        """Verify notification close() lifecycle and onclose event routing."""
        close_called = [False]
        n = Notification("System Maintenance")
        n.onclose = lambda: close_called.__setitem__(0, True)

        n.close()

        self.assertTrue(n.closed)
        self.assertTrue(close_called[0])
        self.assertNotIn(n, DesktopNotificationCenter.get_active_notifications())

    def test_high_speed_notification_dispatch_benchmark(self):
        """
        Benchmark: Execute 50,000 desktop notification creations, tag replacements, and action clicks.
        Asserts duration < 0.15s (> 300,000 ops/sec).
        """
        opts = {"body": "Bench notification body text", "tag": "bench_tag"}

        start_time = time.perf_counter()
        for i in range(50000):
            n = Notification(f"Alert_{i}", opts)
            DesktopNotificationCenter.dispatch_action(n, "click")
        duration = time.perf_counter() - start_time

        total_ops = 50000
        ops_per_sec = total_ops / duration
        latency_us = (duration / total_ops) * 1_000_000

        self.assertLess(duration, 0.20, f"50k Notification ops took {duration*1000:.2f}ms (must be < 200ms)")
        print(f"\n[Sprint 45 Web Notifications Benchmark] {total_ops:,} Desktop System Alerts Processed:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Notification Speed: {ops_per_sec:,.0f} ops/second")
        print(f"  - Average Alert Latency: {latency_us:.2f} µs/op")


if __name__ == "__main__":
    unittest.main()
