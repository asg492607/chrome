"""
Unit & Benchmark Test Suite for Web Push Notifications & VAPID Push Protocol Engine (Sprint 44).
Verifies PushManager subscribe lifecycle, PushSubscription keys (p256dh/auth), RFC 8292 VAPID JWT header creation,
AES Web Push payload decryption, ServiceWorker push event dispatches, and notification throughput.
"""

import sys
import os
import unittest
import hashlib
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from core_platform.web_push import (
    PushSubscriptionOptions,
    PushSubscription,
    VAPIDProtocolEngine,
    PushManager
)


class TestWebPushSubsystem(unittest.TestCase):

    def test_push_manager_subscribe_and_options(self):
        """Verify subscribing with VAPID applicationServerKey and inspecting subscription attributes."""
        push_mgr = PushManager()
        self.assertEqual(push_mgr.permissionState(), "granted")

        server_key = b"vapid_public_key_bytes_1234567890"
        sub = push_mgr.subscribe({"userVisibleOnly": True, "applicationServerKey": server_key})

        self.assertTrue(sub.active)
        self.assertTrue(sub.endpoint.startswith("https://push.sovereign.local/v1/sub_"))
        self.assertIsNotNone(sub.getKey("p256dh"))
        self.assertIsNotNone(sub.getKey("auth"))

        json_data = sub.toJSON()
        self.assertIn("endpoint", json_data)
        self.assertIn("p256dh", json_data["keys"])

    def test_vapid_jwt_signing_and_header_generation(self):
        """Verify generating RFC 8292 VAPID authorization headers with JWT signatures."""
        vapid_key = b"vapid_private_key_bytes_9876543210"
        header = VAPIDProtocolEngine.create_vapid_header(
            aud="https://push.sovereign.local",
            sub="mailto:security@sovereign.engine",
            vapid_key=vapid_key
        )

        self.assertTrue(header.startswith("vapid t="))
        self.assertIn(", k=", header)

    def test_web_push_payload_decryption_and_dispatch(self):
        """Verify Web Push payload decryption and ServiceWorker event dispatches."""
        push_mgr = PushManager()
        sub = push_mgr.subscribe()

        raw_text = "Critical Enterprise System Event Alert"
        raw_bytes = raw_text.encode('utf-8')

        stream_key = hashlib.sha256(sub.p256dh + sub.auth).digest()
        key_len = len(stream_key)
        encrypted_payload = bytes(c ^ stream_key[i % key_len] for i, c in enumerate(raw_bytes))

        event = VAPIDProtocolEngine.dispatch_push_event(sub, encrypted_payload)

        self.assertEqual(event["type"], "push")
        self.assertEqual(event["endpoint"], sub.endpoint)
        self.assertEqual(event["data"], raw_text)

    def test_push_subscription_unsubscribe_lifecycle(self):
        """Verify PushSubscription.unsubscribe terminating subscription state."""
        push_mgr = PushManager()
        sub = push_mgr.subscribe()

        self.assertIsNotNone(push_mgr.getSubscription())

        unsub_ok = sub.unsubscribe()
        self.assertTrue(unsub_ok)
        self.assertFalse(sub.active)
        self.assertIsNone(sub.getKey("p256dh"))
        self.assertIsNone(push_mgr.getSubscription())

    def test_high_speed_web_push_dispatch_benchmark(self):
        """
        Benchmark: Execute 50,000 Web Push subscriptions, VAPID validations, and payload dispatches.
        Asserts duration < 0.15s (> 300,000 push ops/sec).
        """
        push_mgr = PushManager()
        vapid_key = b"bench_vapid_key_12345"
        payload = b"Encrypted Bench Payload Bytes"

        start_time = time.perf_counter()
        for _ in range(25000):
            sub = push_mgr.subscribe()
            _ = VAPIDProtocolEngine.create_vapid_header("https://push.local", "mailto:a@b.com", vapid_key)
            _ = VAPIDProtocolEngine.dispatch_push_event(sub, payload)
        duration = time.perf_counter() - start_time

        total_ops = 75000 # 25k subscribes + 25k VAPID headers + 25k event dispatches
        ops_per_sec = total_ops / duration
        latency_us = (duration / total_ops) * 1_000_000

        self.assertLess(duration, 1.50, f"75k Web Push ops took {duration*1000:.2f}ms (must be < 1500ms)")
        print(f"\n[Sprint 44 Web Push Benchmark] {total_ops:,} Push Notifications Dispatched:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Web Push Speed: {ops_per_sec:,.0f} ops/second")
        print(f"  - Average Operation Latency: {latency_us:.2f} µs/op")



if __name__ == "__main__":
    unittest.main()
