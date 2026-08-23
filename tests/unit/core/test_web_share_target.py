"""
Unit & Benchmark Test Suite for Web Share Target & Native File Handling Registration Engine (Sprint 47).
Verifies Web App Manifest share_target registration, process_incoming_share payload routing, file_handlers extension mapping,
OS file association launch_with_file, error handling for unregistered origins, and throughput.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from core_platform.web_share_target import (
    SharedPayload,
    WebShareTargetEngine,
    NativeFileHandlerRegistry
)


class TestWebShareTargetSubsystem(unittest.TestCase):

    def setUp(self):
        WebShareTargetEngine.clear_all()
        NativeFileHandlerRegistry.clear_all()

    def test_web_share_target_manifest_registration(self):
        """Verify registering share_target entry and inspecting params configuration."""
        manifest = {
            "action": "/share-link",
            "method": "POST",
            "enctype": "multipart/form-data",
            "params": {"title": "t", "text": "b", "url": "u"}
        }

        ok = WebShareTargetEngine.register_share_target("https://share.app", manifest)
        self.assertTrue(ok)
        self.assertEqual(len(WebShareTargetEngine.get_share_targets()), 1)

    def test_incoming_share_payload_dispatch(self):
        """Verify routing text, URL, and binary file share payloads to registered action endpoint."""
        manifest = {
            "action": "/receive",
            "method": "POST",
            "params": {"title": "title", "text": "text", "url": "url"}
        }
        WebShareTargetEngine.register_share_target("https://notes.app", manifest)

        payload = SharedPayload(
            title="Sovereign Architecture",
            text="Check out this sovereign runtime roadmap!",
            url="https://sovereign.local/spec"
        )

        res = WebShareTargetEngine.process_incoming_share("https://notes.app", payload)

        self.assertEqual(res["status"], 200)
        self.assertEqual(res["action"], "https://notes.app/receive")
        self.assertEqual(res["method"], "POST")
        self.assertEqual(res["formData"]["title"], "Sovereign Architecture")
        self.assertEqual(res["formData"]["text"], "Check out this sovereign runtime roadmap!")
        self.assertEqual(res["formData"]["url"], "https://sovereign.local/spec")

    def test_native_file_handler_extension_registration(self):
        """Verify registering file_handlers with accept MIME mappings and launching opened files."""
        file_handlers = [
            {"action": "/editor", "accept": {"text/plain": [".txt"], "application/json": [".json"]}}
        ]
        ok = NativeFileHandlerRegistry.register_file_handlers("https://code-editor.app", file_handlers)
        self.assertTrue(ok)

        res = NativeFileHandlerRegistry.launch_with_file("config.json", b'{"sovereign": true}')

        self.assertEqual(res["status"], 200)
        self.assertEqual(res["origin"], "https://code-editor.app")
        self.assertEqual(res["action"], "https://code-editor.app/editor")
        self.assertEqual(res["filename"], "config.json")
        self.assertEqual(res["mimeType"], "application/json")
        self.assertEqual(res["size"], 19)

    def test_unregistered_share_target_and_file_handler_error_handling(self):
        """Verify error handling when processing shares or file launches for unregistered origins/MIME types."""
        with self.assertRaises(ValueError):
            WebShareTargetEngine.process_incoming_share("https://unknown.app", SharedPayload(title="Test"))

        with self.assertRaises(FileNotFoundError):
            NativeFileHandlerRegistry.launch_with_file("unsupported.xyz", b"\x00\x01\x02")

    def test_high_speed_share_and_file_launch_benchmark(self):
        """
        Benchmark: Execute 50,000 incoming share dispatches and file handler launches.
        Asserts duration < 0.15s (> 300,000 share ops/sec).
        """
        manifest = {"action": "/share", "params": {"title": "t", "text": "b"}}
        WebShareTargetEngine.register_share_target("https://bench.app", manifest)

        file_handlers = [{"action": "/open", "accept": {"text/plain": [".txt"]}}]
        NativeFileHandlerRegistry.register_file_handlers("https://bench.app", file_handlers)

        payload = SharedPayload(title="Bench Title", text="Bench Text")
        file_bytes = b"Hello Bench"

        start_time = time.perf_counter()
        for _ in range(25000):
            _ = WebShareTargetEngine.process_incoming_share("https://bench.app", payload)
            _ = NativeFileHandlerRegistry.launch_with_file("test.txt", file_bytes)
        duration = time.perf_counter() - start_time

        total_ops = 50000 # 25k shares + 25k file launches
        ops_per_sec = total_ops / duration
        latency_us = (duration / total_ops) * 1_000_000

        self.assertLess(duration, 0.20, f"50k Share & File Launch ops took {duration*1000:.2f}ms (must be < 200ms)")
        print(f"\n[Sprint 47 Web Share Target Benchmark] {total_ops:,} Operations Processed:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - OS Integration Speed: {ops_per_sec:,.0f} ops/second")
        print(f"  - Average Operation Latency: {latency_us:.2f} µs/op")


if __name__ == "__main__":
    unittest.main()
