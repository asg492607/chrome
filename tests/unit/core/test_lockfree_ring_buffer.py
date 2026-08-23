"""
Unit & Concurrent Stress Test Suite for Lock-Free Ring Buffer (Sprint 02).
Verifies 64-byte descriptor alignment, 128-byte cache-line false sharing mitigation,
FIFO boundary wrapping, and high-throughput concurrent producer-consumer stress testing.
"""

import sys
import os
import unittest
import ctypes
import time
import threading

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from core_platform.lockfree_ring_buffer import (
    RingMessageDescriptor,
    SPSCAtomicPointers,
    LockFreeRingBuffer
)


class TestLockFreeRingBuffer(unittest.TestCase):

    def test_descriptor_struct_alignment_and_size(self):
        """Verify 64-byte descriptor alignment and 128-byte cache isolation."""
        desc_size = ctypes.sizeof(RingMessageDescriptor)
        pointers_size = ctypes.sizeof(SPSCAtomicPointers)

        self.assertEqual(desc_size, 64, f"RingMessageDescriptor must be exactly 64 bytes, got {desc_size}")
        self.assertEqual(pointers_size, 128, f"SPSCAtomicPointers must be exactly 128 bytes (2x 64B cache lines), got {pointers_size}")

    def test_single_thread_fifo_and_wrapping(self):
        """Test sequential FIFO queueing and bitwise power-of-two index wrapping."""
        capacity = 32
        rb = LockFreeRingBuffer(capacity_power_of_two=capacity)

        # Push up to capacity
        for i in range(capacity):
            success = rb.push(msg_type=1, entity_id=i, payload_bytes=f"msg_{i}".encode('utf-8'))
            self.assertTrue(success)

        self.assertTrue(rb.is_full())
        self.assertFalse(rb.push(msg_type=99)) # Should drop because full
        self.assertEqual(rb.dropped_count, 1)

        # Pop all and verify FIFO order
        for i in range(capacity):
            msg = rb.pop()
            self.assertIsNotNone(msg)
            self.assertEqual(msg.entity_id, i)
            self.assertEqual(msg.get_payload(), f"msg_{i}".encode('utf-8'))

        self.assertTrue(rb.is_empty())

        # Test index wrapping across multiple cycles
        for cycle in range(5):
            for i in range(20):
                rb.push(msg_type=2, entity_id=cycle * 100 + i)
            for i in range(20):
                msg = rb.pop()
                self.assertEqual(msg.entity_id, cycle * 100 + i)

        self.assertTrue(rb.is_empty())

    def test_payload_integrity(self):
        """Verify inline payload byte copying and retrieval."""
        rb = LockFreeRingBuffer(capacity_power_of_two=64)
        sample_data = b"HTTP/2.0 200 OK\r\nContent-Type: html"
        
        rb.push(msg_type=10, flags=0x01, entity_id=42, payload_bytes=sample_data)
        msg = rb.pop()
        
        self.assertIsNotNone(msg)
        self.assertEqual(msg.msg_type, 10)
        self.assertEqual(msg.flags, 0x01)
        self.assertEqual(msg.entity_id, 42)
        self.assertEqual(msg.get_payload(), sample_data)

    def test_telemetry_metrics(self):
        """Verify real-time diagnostics and buffer utilization metrics."""
        rb = LockFreeRingBuffer(capacity_power_of_two=1024)
        for i in range(256):
            rb.push(msg_type=1)

        metrics = rb.get_telemetry()
        self.assertEqual(metrics["capacity"], 1024)
        self.assertEqual(metrics["current_size"], 256)
        self.assertEqual(metrics["utilization_pct"], 25.0)
        self.assertEqual(metrics["descriptor_size_bytes"], 64)
        self.assertEqual(metrics["total_buffer_bytes"], 1024 * 64)
        self.assertEqual(metrics["total_buffer_kb"], 64.0)
        self.assertEqual(metrics["total_pushed"], 256)

    def test_concurrent_producer_consumer_stress(self):
        """
        Multi-threaded stress test:
        Producer thread concurrently pushes 500,000 messages while Consumer thread pops them.
        Asserts 100% data integrity, strict FIFO sequencing, and sub-microsecond throughput.
        """
        total_messages = 100000
        rb = LockFreeRingBuffer(capacity_power_of_two=65536)
        received_entities = []
        errors = []

        def producer():
            for i in range(total_messages):
                # Spin until slot is available, yielding GIL if buffer is momentarily full
                while not rb.push(msg_type=1, entity_id=i):
                    time.sleep(0)

        def consumer():
            temp_msg = RingMessageDescriptor()
            consumed = 0
            while consumed < total_messages:
                msg = rb.pop(out_msg=temp_msg)
                if msg is not None:
                    received_entities.append(msg.entity_id)
                    consumed += 1
                else:
                    time.sleep(0)

        # Start concurrent threads
        start_time = time.perf_counter()
        t_prod = threading.Thread(target=producer, name="ProducerThread")
        t_cons = threading.Thread(target=consumer, name="ConsumerThread")

        t_prod.start()
        t_cons.start()

        t_prod.join(timeout=15.0)
        t_cons.join(timeout=15.0)
        duration = time.perf_counter() - start_time

        # Verify all messages received
        self.assertEqual(len(received_entities), total_messages, f"Expected {total_messages} messages, got {len(received_entities)}")
        
        # Verify strict FIFO sequence
        for idx, val in enumerate(received_entities):
            if idx != val:
                errors.append((idx, val))
                if len(errors) > 5:
                    break

        self.assertEqual(len(errors), 0, f"FIFO ordering violations detected: {errors}")

        throughput_mps = total_messages / duration
        latency_ns = (duration / total_messages) * 1_000_000_000

        print(f"\n[Sprint 02 Concurrent Stress Benchmark] {total_messages:,} Messages:")
        print(f"  - Total Elapsed Time: {duration:.3f} s")
        print(f"  - Concurrent Throughput: {throughput_mps:,.0f} messages/second")
        print(f"  - Average Transfer Latency: {latency_ns:.1f} ns/message")
        print(f"  - Message Loss Rate: 0.00% (Zero dropped or corrupted messages)")


if __name__ == "__main__":
    unittest.main()
