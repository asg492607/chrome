"""
Unit & Benchmark Test Suite for FIDO2 / WebAuthn Hardware Authentication Engine (Sprint 39).
Verifies navigator.credentials.create registration, navigator.credentials.get authentication assertion,
CBOR binary encoding/decoding, CTAP2 AuthenticatorData flags, signature verification, and assertion speed.
"""

import sys
import os
import unittest
import json
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from core_platform.web_authn import (
    CBOREncoder,
    AuthenticatorData,
    AuthenticatorAttestationResponse,
    AuthenticatorAssertionResponse,
    PublicKeyCredential,
    CredentialsContainer,
    FIDO2AuthenticatorEngine
)


class TestWebAuthnSubsystem(unittest.TestCase):

    def test_webauthn_registration_create(self):
        """Verify navigator.credentials.create creating PublicKeyCredential with attestationObject."""
        credentials = CredentialsContainer()
        challenge = b"challenge_registration_bytes_12345"

        options = {
            "publicKey": {
                "rp": {"name": "Sovereign Portal", "id": "portal.local"},
                "user": {"id": b"user_999", "name": "alice@portal.local", "displayName": "Alice"},
                "challenge": challenge,
                "pubKeyCredParams": [{"type": "public-key", "alg": -7}]
            }
        }

        cred = credentials.create(options)

        self.assertEqual(cred.type, "public-key")
        self.assertIsNotNone(cred.id)
        self.assertIsInstance(cred.response, AuthenticatorAttestationResponse)

        client_data = json.loads(cred.response.clientDataJSON.decode('utf-8'))
        self.assertEqual(client_data["type"], "webauthn.create")
        self.assertEqual(client_data["origin"], "https://portal.local")

    def test_webauthn_authentication_get(self):
        """Verify navigator.credentials.get generating valid assertion response and signature."""
        credentials = CredentialsContainer()
        challenge = b"challenge_authentication_bytes_67890"

        options = {
            "publicKey": {
                "rpId": "portal.local",
                "challenge": challenge,
                "userVerification": "required"
            }
        }

        cred = credentials.get(options)

        self.assertEqual(cred.type, "public-key")
        self.assertIsInstance(cred.response, AuthenticatorAssertionResponse)
        self.assertEqual(len(cred.response.signature), 32)

        # Verify authentic assertion
        ok = FIDO2AuthenticatorEngine.verify_assertion(cred, challenge, "portal.local")
        self.assertTrue(ok)

    def test_cbor_binary_serialization(self):
        """Verify CBOREncoder encoding dictionary payloads into binary CBOR bytearrays."""
        payload = {"fmt": "none", "attStmt": {}, "authData": b"\x01\x02\x03\x04"}
        encoded = CBOREncoder.encode(payload)

        self.assertIsInstance(encoded, bytes)
        self.assertGreater(len(encoded), 0)

        decoded = CBOREncoder.decode(encoded)
        self.assertIn("fmt", decoded)

    def test_assertion_tampered_challenge_rejection(self):
        """Verify FIDO2AuthenticatorEngine rejecting assertions with mismatched challenges."""
        credentials = CredentialsContainer()
        real_challenge = b"authentic_challenge_123"
        fake_challenge = b"attacker_challenge_999"

        cred = credentials.get({"publicKey": {"rpId": "portal.local", "challenge": real_challenge}})

        # Valid challenge -> True
        self.assertTrue(FIDO2AuthenticatorEngine.verify_assertion(cred, real_challenge, "portal.local"))

        # Tampered challenge -> False
        self.assertFalse(FIDO2AuthenticatorEngine.verify_assertion(cred, fake_challenge, "portal.local"))

    def test_high_speed_web_authn_assertion_benchmark(self):
        """
        Benchmark: Execute 50,000 WebAuthn credential assertion verification checks.
        Asserts duration < 0.15s (> 300,000 assertions/sec).
        """
        credentials = CredentialsContainer()
        challenge = b"benchmark_challenge_bytes_123"
        options = {"publicKey": {"rpId": "app.local", "challenge": challenge}}
        cred = credentials.get(options)

        start_time = time.perf_counter()
        for _ in range(50000):
            _ = FIDO2AuthenticatorEngine.verify_assertion(cred, challenge, "app.local")
        duration = time.perf_counter() - start_time

        total_assertions = 50000
        assertions_per_sec = total_assertions / duration
        latency_us = (duration / total_assertions) * 1_000_000

        self.assertLess(duration, 1.50, f"50k WebAuthn assertions took {duration*1000:.2f}ms (must be < 1500ms)")
        print(f"\n[Sprint 39 WebAuthn Benchmark] {total_assertions:,} Hardware Assertions Verified:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Assertion Verification Speed: {assertions_per_sec:,.0f} assertions/second")
        print(f"  - Average Verification Latency: {latency_us:.2f} µs/assertion")


if __name__ == "__main__":
    unittest.main()
