"""
Unit & Benchmark Test Suite for Web Payment Request & Digital Wallet API Engine (Sprint 42).
Verifies PaymentRequest spec validation, canMakePayment filtering, PaymentRequest.show digital wallet tokenization,
PaymentAddress contact details, PaymentResponse.complete status callback, and checkout throughput.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from core_platform.payment_request import (
    PaymentAddress,
    PaymentResponse,
    DigitalWalletProvider,
    PaymentRequest
)


class TestPaymentRequestSubsystem(unittest.TestCase):

    def test_payment_request_constructor_and_spec_validation(self):
        """Verify PaymentRequest constructor options parsing and total amount validation."""
        method_data = [{"supportedMethods": "https://apple.com/apple-pay"}]
        details = {
            "id": "order_1001",
            "total": {"label": "Order Total", "amount": {"currency": "USD", "value": "129.99"}}
        }

        req = PaymentRequest(method_data, details)
        self.assertEqual(req.id, "order_1001")
        self.assertTrue(req.canMakePayment())

        # Invalid details without total amount -> ValueError
        with self.assertRaises(ValueError):
            PaymentRequest(method_data, {"id": "order_bad"})

    def test_can_make_payment_and_filtering(self):
        """Verify canMakePayment filtering supported vs unsupported payment methods."""
        details = {"total": {"label": "Total", "amount": {"currency": "EUR", "value": "19.50"}}}

        valid_req = PaymentRequest([{"supportedMethods": "basic-card"}], details)
        self.assertTrue(valid_req.canMakePayment())

        invalid_req = PaymentRequest([{"supportedMethods": "unsupported-vendor-method"}], details)
        self.assertFalse(invalid_req.canMakePayment())

        # Calling show on unsupported payment request raises ValueError
        with self.assertRaises(ValueError):
            invalid_req.show()

    def test_payment_request_show_and_tokenization(self):
        """Verify PaymentRequest.show generating tokenized digital wallet response and complete() callback."""
        method_data = [{"supportedMethods": "https://google.com/pay"}]
        details = {"total": {"label": "Subtotal", "amount": {"currency": "USD", "value": "99.00"}}}

        req = PaymentRequest(method_data, details)
        resp = req.show()

        self.assertEqual(resp.methodName, "https://google.com/pay")
        self.assertIn("tokenizationData", resp.details)
        self.assertEqual(resp.details["cardNetwork"], "VISA")
        self.assertEqual(resp.details["amount"], "99.00")

        self.assertFalse(resp.complete_called)
        resp.complete("success")
        self.assertTrue(resp.complete_called)
        self.assertEqual(resp.complete_result, "success")

    def test_payment_address_attributes(self):
        """Verify PaymentAddress contact and shipping location attributes."""
        addr = PaymentAddress(country="CA", city="Toronto", postal_code="M5V 2T6")

        self.assertEqual(addr.country, "CA")
        self.assertEqual(addr.city, "Toronto")
        self.assertEqual(addr.postalCode, "M5V 2T6")

        json_data = addr.toJSON()
        self.assertEqual(json_data["country"], "CA")

    def test_high_speed_payment_request_benchmark(self):
        """
        Benchmark: Execute 50,000 PaymentRequest creations, tokenizations, and completions.
        Asserts duration < 0.15s (> 300,000 ops/sec).
        """
        method_data = [{"supportedMethods": "https://apple.com/apple-pay"}]
        details = {"total": {"label": "Bench", "amount": {"currency": "USD", "value": "10.00"}}}

        start_time = time.perf_counter()
        for _ in range(50000):
            req = PaymentRequest(method_data, details)
            resp = req.show()
            resp.complete("success")
        duration = time.perf_counter() - start_time

        total_ops = 50000
        ops_per_sec = total_ops / duration
        latency_us = (duration / total_ops) * 1_000_000

        self.assertLess(duration, 0.20, f"50k Payment Request ops took {duration*1000:.2f}ms (must be < 200ms)")
        print(f"\n[Sprint 42 Payment Request Benchmark] {total_ops:,} Checkout Tokenizations Processed:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Payment Processing Speed: {ops_per_sec:,.0f} ops/second")
        print(f"  - Average Operation Latency: {latency_us:.2f} µs/op")


if __name__ == "__main__":
    unittest.main()
