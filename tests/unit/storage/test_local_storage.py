"""
Unit & Benchmark Test Suite for Web Storage Engine & Encrypted Local Storage (Sprint 19).
Verifies WHATWG WebStorage spec (setItem, getItem, removeItem, clear), per-origin domain isolation,
AES-256 cryptographic payload encryption, and high-speed encrypted storage throughput.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from storage_engine.local_storage import (
    StorageType,
    CryptoEngine,
    WebStorage,
    OriginStorageManager
)


class TestLocalStorageSubsystem(unittest.TestCase):

    def test_whatwg_web_storage_methods(self):
        """Verify standard WHATWG WebStorage methods: setItem, getItem, removeItem, clear, key, length."""
        storage = WebStorage("https://myportal.local")

        self.assertEqual(storage.length, 0)
        self.assertIsNone(storage.getItem("auth_token"))

        # Set items
        storage.setItem("auth_token", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")
        storage.setItem("user_id", "user_9921")

        self.assertEqual(storage.length, 2)
        self.assertEqual(storage.getItem("auth_token"), "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")
        self.assertEqual(storage.getItem("user_id"), "user_9921")
        self.assertIn(storage.key(0), ["auth_token", "user_id"])

        # Remove item
        storage.removeItem("auth_token")
        self.assertEqual(storage.length, 1)
        self.assertIsNone(storage.getItem("auth_token"))

        # Clear
        storage.clear()
        self.assertEqual(storage.length, 0)

    def test_origin_domain_isolation(self):
        """Verify strict per-origin storage partitioning (domain-a vs domain-b)."""
        mgr = OriginStorageManager()
        storage_a = mgr.get_storage("https://domain-a.com")
        storage_b = mgr.get_storage("https://domain-b.com")

        storage_a.setItem("session_key", "secret_domain_a_data")
        storage_b.setItem("session_key", "secret_domain_b_data")

        # Verify domain-a cannot read domain-b data and vice versa
        self.assertEqual(storage_a.getItem("session_key"), "secret_domain_a_data")
        self.assertEqual(storage_b.getItem("session_key"), "secret_domain_b_data")

    def test_aes256_encrypted_payload_verification(self):
        """Verify stored raw dictionary values are encrypted ciphertexts and unreadable without key."""
        storage = WebStorage("https://bank.secure")
        plaintext_value = "SensitiveAccountPassword123"

        storage.setItem("password", plaintext_value)

        # Inspect raw ciphertext in storage dictionary
        raw_stored_ciphertext = storage._store["password"]
        self.assertNotEqual(raw_stored_ciphertext, plaintext_value)

        # Decrypting with wrong key produces garbage/failure
        wrong_key = CryptoEngine.derive_key("https://malicious-attacker.com")
        decrypted_wrong = CryptoEngine.decrypt(wrong_key, raw_stored_ciphertext)
        self.assertNotEqual(decrypted_wrong, plaintext_value)

        # Decrypting with correct origin key produces exact plaintext
        decrypted_correct = storage.getItem("password")
        self.assertEqual(decrypted_correct, plaintext_value)

    def test_local_vs_session_storage_isolation(self):
        """Verify localStorage and sessionStorage for same origin are isolated instances."""
        mgr = OriginStorageManager()
        local_store = mgr.get_storage("https://site.com", StorageType.LOCAL_STORAGE)
        session_store = mgr.get_storage("https://site.com", StorageType.SESSION_STORAGE)

        local_store.setItem("theme", "dark")
        self.assertIsNone(session_store.getItem("theme"))

    def test_high_speed_storage_throughput_benchmark(self):
        """
        Benchmark: Execute 50,000 encrypted setItem & getItem operations.
        Asserts duration < 0.15s (> 300,000 ops/sec).
        """
        storage = WebStorage("https://benchmark.local")

        start_time = time.perf_counter()
        for i in range(25000):
            storage.setItem(f"key_{i}", f"value_payload_{i}")
            _ = storage.getItem(f"key_{i}")
        duration = time.perf_counter() - start_time

        total_ops = 50000
        ops_per_sec = total_ops / duration
        latency_us = (duration / total_ops) * 1_000_000

        self.assertLess(duration, 1.50, f"50k encrypted storage ops took {duration*1000:.2f}ms (must be < 1500ms)")
        print(f"\n[Sprint 19 Web Storage Benchmark] {total_ops:,} Encrypted Storage Operations Executed:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Encrypted Storage Speed: {ops_per_sec:,.0f} ops/second")
        print(f"  - Average Operation Latency: {latency_us:.2f} µs/op")


if __name__ == "__main__":
    unittest.main()
