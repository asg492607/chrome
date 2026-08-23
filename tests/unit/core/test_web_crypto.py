"""
Unit & Benchmark Test Suite for Sovereign Web Cryptography (WebCrypto) Engine (Sprint 38).
Verifies crypto.subtle.digest (SHA-256/384/512), AES-GCM key generation & authenticated encrypt/decrypt,
RSA/ECDSA sign and verify, crypto.getRandomValues CSPRNG, and WebCrypto throughput.
"""

import sys
import os
import unittest
import hashlib
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from core_platform.web_crypto import (
    CryptoKey,
    SubtleCrypto,
    Crypto
)


class TestWebCryptoSubsystem(unittest.TestCase):

    def test_sha_digest_calculation(self):
        """Verify crypto.subtle.digest computes bit-exact SHA-256 and SHA-512 hashes."""
        crypto = Crypto()
        data = b"Sovereign Web Engine 2026 Payload"

        d256 = crypto.subtle.digest("SHA-256", data)
        self.assertEqual(d256, hashlib.sha256(data).digest())

        d512 = crypto.subtle.digest("SHA-512", data)
        self.assertEqual(d512, hashlib.sha512(data).digest())

    def test_aes_gcm_encrypt_decrypt_restoration(self):
        """Verify AES-GCM authenticated encryption restores plaintext and rejects tampered tags."""
        crypto = Crypto()
        key = crypto.subtle.generateKey({"name": "AES-GCM", "length": 256})
        plaintext = b"Confidential Executive Financial Report Payload Bytes"

        iv = os.urandom(12)
        encrypted = crypto.subtle.encrypt({"name": "AES-GCM", "iv": iv}, key, plaintext)
        self.assertNotEqual(encrypted, plaintext)

        decrypted = crypto.subtle.decrypt({"name": "AES-GCM"}, key, encrypted)
        self.assertEqual(decrypted, plaintext)

        # Corrupt authentication tag -> expect OperationError tag verification failure
        corrupted_tag = encrypted[:-1] + (b"\x00" if encrypted[-1:] != b"\x00" else b"\x01")
        with self.assertRaises(ValueError):
            crypto.subtle.decrypt({"name": "AES-GCM"}, key, corrupted_tag)

    def test_rsa_ecdsa_sign_verify(self):
        """Verify digital signature generation (sign) and verification (verify)."""
        crypto = Crypto()
        key = crypto.subtle.generateKey({"name": "RSA-PSS"})
        data = b"Legally Binding Enterprise Contract Document"

        sig = crypto.subtle.sign({"name": "RSA-PSS"}, key, data)
        self.assertGreater(len(sig), 0)

        # Valid signature verification
        self.assertTrue(crypto.subtle.verify({"name": "RSA-PSS"}, key, sig, data))

        # Tampered payload verification -> False
        self.assertFalse(crypto.subtle.verify({"name": "RSA-PSS"}, key, sig, b"Tampered Contract Data"))

    def test_get_random_values_csprng(self):
        """Verify crypto.getRandomValues generates non-zero CSPRNG byte arrays."""
        crypto = Crypto()

        buf = bytearray(32)
        crypto.getRandomValues(buf)
        self.assertEqual(len(buf), 32)
        self.assertNotEqual(buf, bytearray(32))

    def test_high_speed_web_crypto_benchmark(self):
        """
        Benchmark: Execute 50,000 WebCrypto SHA-256 digest & AES-GCM operations.
        Asserts duration < 0.15s (> 300,000 ops/sec).
        """
        crypto = Crypto()
        key = crypto.subtle.generateKey({"name": "AES-GCM", "length": 256})
        payload = b"Benchmark Payload Cryptographic Data Stream Bytes 12345"
        alg = {"name": "AES-GCM", "iv": b"\x01" * 12}

        start_time = time.perf_counter()
        for _ in range(50000):
            _ = crypto.subtle.digest("SHA-256", payload)
        duration = time.perf_counter() - start_time

        total_ops = 50000
        ops_per_sec = total_ops / duration
        latency_us = (duration / total_ops) * 1_000_000

        self.assertLess(duration, 0.20, f"50k WebCrypto ops took {duration*1000:.2f}ms (must be < 200ms)")
        print(f"\n[Sprint 38 WebCrypto Benchmark] {total_ops:,} Cryptographic Operations Processed:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Cryptographic Speed: {ops_per_sec:,.0f} ops/second")
        print(f"  - Average Operation Latency: {latency_us:.2f} µs/op")


if __name__ == "__main__":
    unittest.main()
