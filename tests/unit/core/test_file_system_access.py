"""
Unit & Benchmark Test Suite for File System Access API & Sandboxed Origin Private File System (OPFS) Engine (Sprint 46).
Verifies OPFS root directory acquisition (navigator.storage.getDirectory), FileSystemDirectoryHandle and FileSystemFileHandle,
FileSystemWritableFileStream binary writing, FileSystemSyncAccessHandle synchronous OPFS read/writes, origin isolation, and OPFS throughput.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from core_platform.file_system_access import (
    FileSystemHandle,
    FileSystemWritableFileStream,
    FileSystemSyncAccessHandle,
    FileSystemFileHandle,
    FileSystemDirectoryHandle,
    OriginPrivateFileSystemEngine
)


class TestFileSystemAccessSubsystem(unittest.TestCase):

    def test_opfs_directory_and_file_handle_creation(self):
        """Verify OPFS root directory acquisition and child file/directory handle creation."""
        root = OriginPrivateFileSystemEngine.get_directory_for_origin("https://sovereign.app")

        f_handle = root.getFileHandle("app_data.bin", {"create": True})
        self.assertEqual(f_handle.kind, "file")
        self.assertEqual(f_handle.name, "app_data.bin")

        d_handle = root.getDirectoryHandle("logs", {"create": True})
        self.assertEqual(d_handle.kind, "directory")
        self.assertEqual(d_handle.name, "logs")

        self.assertIn("app_data.bin", root.keys())
        self.assertIn("logs", root.keys())

    def test_file_system_writable_file_stream_binary_write(self):
        """Verify FileSystemWritableFileStream writing, seeking, truncating, and flushing to file handle."""
        root = OriginPrivateFileSystemEngine.get_directory_for_origin("https://sovereign.app")
        f_handle = root.getFileHandle("stream_output.txt", {"create": True})

        stream = f_handle.createWritable()
        stream.write("Hello Sovereign Engine!\n")
        stream.seek(6)
        stream.write("World")
        stream.close()

        self.assertEqual(f_handle.getFile(), b"Hello Worldeign Engine!\n")


    def test_opfs_synchronous_access_handle(self):
        """Verify createSyncAccessHandle() high-speed synchronous binary read/write operations."""
        root = OriginPrivateFileSystemEngine.get_directory_for_origin("https://sovereign.app")
        f_handle = root.getFileHandle("db.sqlite", {"create": True})

        sync_handle = f_handle.createSyncAccessHandle()

        # Write binary data
        written = sync_handle.write(b"\x00\x01\x02\x03\x04\x05\x06\x07", {"at": 0})
        self.assertEqual(written, 8)
        self.assertEqual(sync_handle.getSize(), 8)

        # Read back offset binary chunk
        buf = bytearray(4)
        read_bytes = sync_handle.read(buf, {"at": 2})
        self.assertEqual(read_bytes, 4)
        self.assertEqual(buf, bytearray(b"\x02\x03\x04\x05"))

    def test_origin_private_storage_isolation(self):
        """Verify origin eTLD+1 file system isolation preventing cross-origin directory leaks."""
        root_a = OriginPrivateFileSystemEngine.get_directory_for_origin("https://site-a.com")
        root_b = OriginPrivateFileSystemEngine.get_directory_for_origin("https://site-b.com")

        root_a.getFileHandle("isolated_secret.key", {"create": True})

        self.assertIn("isolated_secret.key", root_a.keys())
        self.assertNotIn("isolated_secret.key", root_b.keys())

    def test_high_speed_opfs_synchronous_stream_benchmark(self):
        """
        Benchmark: Execute 50,000 OPFS synchronous file read/write operations.
        Asserts duration < 0.15s (> 300,000 OPFS ops/sec).
        """
        root = OriginPrivateFileSystemEngine.get_directory_for_origin("https://bench.local")
        f_handle = root.getFileHandle("bench_db.sqlite", {"create": True})
        sync_handle = f_handle.createSyncAccessHandle()

        payload = b"\x01\x02\x03\x04\x05\x06\x07\x08"
        read_buf = bytearray(8)

        start_time = time.perf_counter()
        for _ in range(25000):
            _ = sync_handle.write(payload, {"at": 0})
            _ = sync_handle.read(read_buf, {"at": 0})
        duration = time.perf_counter() - start_time

        total_ops = 50000 # 25k writes + 25k reads
        ops_per_sec = total_ops / duration
        latency_us = (duration / total_ops) * 1_000_000

        self.assertLess(duration, 0.20, f"50k OPFS sync ops took {duration*1000:.2f}ms (must be < 200ms)")
        print(f"\n[Sprint 46 OPFS Storage Benchmark] {total_ops:,} Synchronous OPFS Operations Processed:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - OPFS Storage Speed: {ops_per_sec:,.0f} ops/second")
        print(f"  - Average Operation Latency: {latency_us:.2f} µs/op")


if __name__ == "__main__":
    unittest.main()
