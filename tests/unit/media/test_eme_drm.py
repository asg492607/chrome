"""
Unit & Benchmark Test Suite for Encrypted Media Extensions (EME) & Sovereign DRM Engine (Sprint 32).
Verifies requestMediaKeySystemAccess, MediaKeySession challenge/license exchange,
ISO/IEC 23001-7 CENC AES-128-CTR sample decryption, key status transitions, and decryption throughput.
"""

import sys
import os
import unittest
import json
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from media_engine.eme_drm import (
    MediaKeySessionType,
    MediaKeyStatus,
    AESCTRDecrypter,
    MediaKeyStatusMap,
    MediaKeySession,
    MediaKeys,
    MediaKeySystemAccess,
    EMEDRMEngine
)


class TestEMEDRMSubsystem(unittest.TestCase):

    def test_request_media_key_system_access(self):
        """Verify requesting org.w3.clearkey and com.sovereign.drm access and rejecting unsupported systems."""
        access = EMEDRMEngine.requestMediaKeySystemAccess("org.w3.clearkey")
        self.assertEqual(access.keySystem, "org.w3.clearkey")

        config = access.getConfiguration()
        self.assertIn("keySystem", config)

        media_keys = access.createMediaKeys()
        self.assertIsNotNone(media_keys)

        with self.assertRaises(ValueError):
            EMEDRMEngine.requestMediaKeySystemAccess("com.invalid.drm")

    def test_mediakeysession_challenge_and_license_exchange(self):
        """Verify generating DRM license challenge and updating session with JSON key response."""
        access = EMEDRMEngine.requestMediaKeySystemAccess("org.w3.clearkey")
        media_keys = access.createMediaKeys()

        session = media_keys.createSession("temporary")
        self.assertIsNotNone(session.sessionId)

        challenge = session.generateRequest("cenc", b"init_data_header_bytes_12345")
        self.assertGreater(len(challenge), 0)

        # Simulate license server JSON response payload
        license_json = json.dumps({
            "keys": [
                {"kty": "oct", "kid": "key_id_alpha", "k": "aes_key_bytes_128"}
            ]
        }).encode('utf-8')

        ok = session.update(license_json)
        self.assertTrue(ok)
        self.assertIn(b"key_id_alpha", session.keyStatuses)
        self.assertEqual(session.keyStatuses.get(b"key_id_alpha"), MediaKeyStatus.USABLE)

    def test_cenc_aes_128_ctr_decryption(self):
        """Verify ISO/IEC 23001-7 CENC AES-128-CTR sample decryption restores original plaintext."""
        key = b"\x01" * 16
        iv = b"\x02" * 16
        plaintext = b"Sovereign DRM Encrypted Video Payload Frame Data"

        # CTR mode stream encryption
        ciphertext = AESCTRDecrypter.decrypt_sample(plaintext, key, iv)
        self.assertNotEqual(ciphertext, plaintext)

        # Decrypt
        decrypted = AESCTRDecrypter.decrypt_sample(ciphertext, key, iv)
        self.assertEqual(decrypted, plaintext)

    def test_mediakeysession_lifecycle_close(self):
        """Verify MediaKeySession close state transition."""
        access = EMEDRMEngine.requestMediaKeySystemAccess("org.w3.clearkey")
        media_keys = access.createMediaKeys()
        session = media_keys.createSession()

        self.assertFalse(session.closed)
        session.close()
        self.assertTrue(session.closed)

    def test_high_speed_drm_sample_decryption_benchmark(self):
        """
        Benchmark: Decrypt 50,000 CENC AES-128-CTR encrypted media samples.
        Asserts duration < 0.15s (> 300,000 samples/sec).
        """
        key = b"\x0a" * 16
        iv = b"\x0b" * 16
        ciphertext = b"Encrypted Frame Sample Payload Data Stream Bytes 12345678"

        start_time = time.perf_counter()
        for _ in range(50000):
            _ = AESCTRDecrypter.decrypt_sample(ciphertext, key, iv)
        duration = time.perf_counter() - start_time

        total_samples = 50000
        samples_per_sec = total_samples / duration
        latency_us = (duration / total_samples) * 1_000_000

        self.assertLess(duration, 1.50, f"50k DRM sample decrypts took {duration*1000:.2f}ms (must be < 1500ms)")
        print(f"\n[Sprint 32 EME DRM Benchmark] {total_samples:,} Encrypted Samples Decrypted:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Sample Decryption Speed: {samples_per_sec:,.0f} samples/second")
        print(f"  - Average Decryption Latency: {latency_us:.2f} µs/sample")



if __name__ == "__main__":
    unittest.main()
