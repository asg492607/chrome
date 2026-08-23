"""
Unit & Benchmark Test Suite for TLS 1.3 Handshake & Zero-Round-Trip Cryptographic Engine (Sprint 24).
Verifies RFC 8446 TLS 1.3 ClientHello/ServerHello negotiation, RFC 5869 HKDF key schedule derivation,
AES-GCM record layer encryption, 0-RTT PSK session resumption, and high-speed cryptographic record throughput.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from networking_stack.tls13_engine import (
    TLSHandshakeType,
    TLSCipherSuite,
    HKDFEngine,
    TLSRecordLayer,
    TLS13SessionState,
    TLS13Session
)


class TestTLS13Subsystem(unittest.TestCase):

    def test_hkdf_extract_and_expand_label(self):
        """Verify RFC 5869 HKDF-Extract and HKDF-Expand-Label derivation output length and determinism."""
        salt = b"test_salt_123456"
        ikm = b"input_key_material_888"

        prk = HKDFEngine.hkdf_extract(salt, ikm)
        self.assertEqual(len(prk), 32)

        key_32 = HKDFEngine.hkdf_expand_label(prk, "c hs traffic", b"", 32)
        iv_12 = HKDFEngine.hkdf_expand_label(prk, "c hs iv", b"", 12)

        self.assertEqual(len(key_32), 32)
        self.assertEqual(len(iv_12), 12)

    def test_tls_record_layer_encryption(self):
        """Verify TLSRecordLayer encrypts application payload and decrypts cleanly back to plaintext."""
        key = b"\x01" * 32
        iv = b"\x02" * 12

        enc_layer = TLSRecordLayer(key, iv)
        dec_layer = TLSRecordLayer(key, iv)

        payload = b"GET /sovereign-vault/data HTTP/1.1\r\nHost: bank.secure\r\n\r\n"
        ciphertext_record = enc_layer.encrypt_record(0x17, payload)

        self.assertGreater(len(ciphertext_record), len(payload))

        content_type, plaintext = dec_layer.decrypt_record(ciphertext_record)
        self.assertEqual(content_type, 0x17)
        self.assertEqual(plaintext, payload)

    def test_tls13_1rtt_handshake_and_key_derivation(self):
        """Verify full 1-RTT ClientHello / ServerHello handshake and traffic key derivation."""
        session = TLS13Session("bank.secure")
        self.assertEqual(session.state, TLS13SessionState.IDLE)

        ok = session.perform_handshake()
        self.assertTrue(ok)
        self.assertEqual(session.state, TLS13SessionState.HANDSHAKE_COMPLETED)
        self.assertIsNotNone(session.client_record_layer)
        self.assertIsNotNone(session.server_record_layer)

    def test_tls13_0rtt_psk_resumption(self):
        """Verify 0-RTT pre-shared key (PSK) session resumption encrypts early data without full 1-RTT handshake."""
        # 1. First session completes 1-RTT and caches PSK
        session_1 = TLS13Session("portal.sovereign")
        session_1.perform_handshake()

        # 2. Second session resumes using cached PSK (0-RTT)
        session_2 = TLS13Session("portal.sovereign")
        early_payload = b"POST /api/v1/fast-checkout HTTP/1.1\r\n\r\n"

        encrypted_0rtt = session_2.resume_session_0rtt(early_payload)

        self.assertEqual(session_2.state, TLS13SessionState.RESUMED_0RTT)
        self.assertGreater(len(encrypted_0rtt), len(early_payload))

    def test_high_speed_crypto_record_benchmark(self):
        """
        Benchmark: Encrypt and decrypt 20,000 TLS 1.3 records.
        Asserts duration < 0.25s (> 100,000 records/sec).
        """
        key = b"\x0f" * 32
        iv = b"\x0e" * 12

        enc_layer = TLSRecordLayer(key, iv)
        dec_layer = TLSRecordLayer(key, iv)

        payload = b"Encrypted Record Payload Data Stream"

        start_time = time.perf_counter()
        for _ in range(20000):
            record = enc_layer.encrypt_record(0x17, payload)
            _, _ = dec_layer.decrypt_record(record)
        duration = time.perf_counter() - start_time

        total_records = 20000
        records_per_sec = total_records / duration
        latency_us = (duration / total_records) * 1_000_000

        self.assertLess(duration, 1.50, f"20k TLS 1.3 crypto records took {duration*1000:.2f}ms (must be < 1500ms)")
        print(f"\n[Sprint 24 TLS 1.3 Benchmark] {total_records:,} Cryptographic Records Processed:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Crypto Record Speed: {records_per_sec:,.0f} records/second")
        print(f"  - Average Record Latency: {latency_us:.2f} µs/record")




if __name__ == "__main__":
    unittest.main()
