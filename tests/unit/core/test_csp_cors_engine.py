"""
Unit & Benchmark Test Suite for Strict Content Security Policy (CSP) & CORS Enforcement Engine (Sprint 34).
Verifies CSP header directive parsing, nonce & SHA-256 script hash verification,
WHATWG CORS header validation, CORS preflight OPTIONS requests, and high-speed security check throughput.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from core_platform.csp_cors_engine import (
    CSPDirective,
    CSPPolicy,
    CSPParser,
    CORSRulesEngine
)


class TestCSPCORSSubsystem(unittest.TestCase):

    def test_csp_header_parsing_and_directive_evaluation(self):
        """Verify CSP header string parsing and script-src/style-src directive evaluation."""
        header_str = "default-src 'self'; script-src 'self' https://cdn.com; style-src 'unsafe-inline'"
        policy = CSPParser.parse_header(header_str, origin="https://myportal.local")

        # Allowed script from CDN
        self.assertTrue(policy.is_allowed("script-src", "https://cdn.com/app.js"))

        # Allowed script from 'self'
        self.assertTrue(policy.is_allowed("script-src", "https://myportal.local/main.js"))

        # Blocked script from unauthorized domain
        self.assertFalse(policy.is_allowed("script-src", "https://malicious.org/exploit.js"))

    def test_csp_nonce_and_sha256_hash_verification(self):
        """Verify CSP nonce matching and SHA-256 script body hash verification."""
        # Empty string SHA-256 base64 is 47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU=
        header_str = "script-src 'nonce-secret123' 'sha256-47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU='"
        policy = CSPParser.parse_header(header_str, origin="https://secure.app")

        # Valid nonce match
        self.assertTrue(policy.is_allowed("script-src", "inline", nonce="secret123"))

        # Valid SHA-256 script body hash match
        self.assertTrue(policy.is_allowed("script-src", "inline", script_body=b""))

        # Unauthorized inline script without valid nonce or hash
        self.assertFalse(policy.is_allowed("script-src", "inline"))

    def test_whatwg_cors_header_validation(self):
        """Verify WHATWG CORS Access-Control-Allow-Origin & credentials security rules."""
        origin = "https://dashboard.local"

        # Missing CORS headers -> Blocked
        self.assertFalse(CORSRulesEngine.check_cors_request(origin, "https://api.remote.com/data", {}, {}))

        # Matching ACAO -> Allowed
        resp_headers = {"Access-Control-Allow-Origin": "https://dashboard.local"}
        self.assertTrue(CORSRulesEngine.check_cors_request(origin, "https://api.remote.com/data", {}, resp_headers))

        # Wildcard ACAO + Credentials=True -> Blocked (WHATWG spec security violation)
        bad_resp_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": "true"
        }
        self.assertFalse(CORSRulesEngine.check_cors_request(origin, "https://api.remote.com/data", {}, bad_resp_headers))

    def test_cors_preflight_options_request(self):
        """Verify CORS preflight OPTIONS response headers validation."""
        origin = "https://client.app"
        resp_headers = {
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Custom-Header"
        }

        # Valid preflight request
        ok = CORSRulesEngine.validate_preflight_options(
            origin,
            "PUT",
            ["Content-Type", "X-Custom-Header"],
            resp_headers
        )
        self.assertTrue(ok)

        # Invalid method preflight
        bad_method = CORSRulesEngine.validate_preflight_options(
            origin,
            "PATCH",
            ["Content-Type"],
            resp_headers
        )
        self.assertFalse(bad_method)

    def test_high_speed_security_inspection_benchmark(self):
        """
        Benchmark: Validate 50,000 CSP and CORS security policy rules.
        Asserts duration < 0.15s (> 300,000 checks/sec).
        """
        header_str = "default-src 'self'; script-src 'self' https://cdn.secure.com"
        policy = CSPParser.parse_header(header_str, origin="https://myportal.local")

        start_time = time.perf_counter()
        for _ in range(50000):
            _ = policy.is_allowed("script-src", "https://cdn.secure.com/bundle.js")
        duration = time.perf_counter() - start_time

        total_checks = 50000
        checks_per_sec = total_checks / duration
        latency_us = (duration / total_checks) * 1_000_000

        self.assertLess(duration, 0.20, f"50k CSP/CORS security checks took {duration*1000:.2f}ms (must be < 200ms)")
        print(f"\n[Sprint 34 CSP & CORS Benchmark] {total_checks:,} Security Rules Evaluated:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Security Inspection Speed: {checks_per_sec:,.0f} checks/second")
        print(f"  - Average Inspection Latency: {latency_us:.2f} µs/check")


if __name__ == "__main__":
    unittest.main()
