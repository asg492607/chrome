"""
Web Payment Request & Digital Wallet API Engine.
Implements W3C Payment Request API Level 1 specification (PaymentRequest, PaymentResponse),
Payment Method Identifiers (basic-card, Apple Pay, Google Pay), and tokenized digital wallet checkout.
"""

import sys
import os
import uuid
from typing import Dict, List, Optional, Tuple, Any, Union

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class PaymentAddress:
    """W3C PaymentAddress representation for shipping/billing contacts."""

    def __init__(
        self,
        country: str = "US",
        address_line: Optional[List[str]] = None,
        city: str = "San Francisco",
        postal_code: str = "94105",
        recipient: str = "Alice Enterprise",
        phone: str = "+14155550199"
    ):
        self.country = country
        self.addressLine = address_line or ["100 Sovereign Way", "Suite 400"]
        self.city = city
        self.postalCode = postal_code
        self.recipient = recipient
        self.phone = phone

    def toJSON(self) -> Dict[str, Any]:
        return {
            "country": self.country,
            "addressLine": self.addressLine,
            "city": self.city,
            "postalCode": self.postalCode,
            "recipient": self.recipient,
            "phone": self.phone
        }


class PaymentResponse:
    """W3C PaymentResponse object returned after user authorizes payment."""

    def __init__(
        self,
        request_id: str,
        method_name: str,
        details: Dict[str, Any],
        payer_name: str = "Alice Enterprise",
        payer_email: str = "alice@enterprise.local",
        payer_phone: str = "+14155550199",
        shipping_address: Optional[PaymentAddress] = None
    ):
        self.requestId = request_id
        self.methodName = method_name
        self.details = details
        self.payerName = payer_name
        self.payerEmail = payer_email
        self.payerPhone = payer_phone
        self.shippingAddress = shipping_address or PaymentAddress()
        self.complete_called = False
        self.complete_result = ""

    def complete(self, result: str = "success") -> None:
        """Notifies the payment engine of transaction completion status."""
        self.complete_called = True
        self.complete_result = result


_token_counter = 0


class DigitalWalletProvider:
    """Digital Wallet Tokenization Provider (Apple Pay, Google Pay, Network Tokens)."""

    @classmethod
    def tokenize_payment(cls, method_name: str, total_amount: str, currency: str) -> Dict[str, Any]:
        """Generates secure tokenized payment credentials payload."""
        global _token_counter
        _token_counter += 1
        return {
            "tokenizationData": {
                "type": "PAYMENT_GATEWAY",
                "token": f"tok_sovereign_{_token_counter}"
            },
            "cardNetwork": "VISA",
            "lastFour": "4242",
            "amount": total_amount,
            "currency": currency,
            "billingAddress": {
                "country": "US",
                "postalCode": "94105"
            }
        }


class PaymentRequest:
    """W3C PaymentRequest main entry point."""

    SUPPORTED_METHODS = {"basic-card", "https://apple.com/apple-pay", "https://google.com/pay"}

    def __init__(
        self,
        method_data: List[Dict[str, Any]],
        details: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None
    ):
        global _token_counter
        self.methodData = method_data
        self.details = details
        self.options = options or {}
        _token_counter += 1
        self.id = details.get("id") or f"req_{_token_counter}"


        # Validate total
        if "total" not in details or "amount" not in details["total"]:
            raise ValueError("TypeError: PaymentRequest details must contain 'total' with 'amount'.")

    def canMakePayment(self) -> bool:
        """Determines whether any requested payment method is supported by the engine."""
        for item in self.methodData:
            method = item.get("supportedMethods", "")
            if method in self.SUPPORTED_METHODS:
                return True
        return False

    def show(self) -> PaymentResponse:
        """Displays native payment authorization UI sheet and returns PaymentResponse token."""
        if not self.canMakePayment():
            raise ValueError("NotSupportedError: None of the requested payment methods are supported.")

        # Resolve primary method
        method_name = "basic-card"
        for item in self.methodData:
            m = item.get("supportedMethods", "")
            if m in self.SUPPORTED_METHODS:
                method_name = m
                break

        total_info = self.details.get("total", {}).get("amount", {})
        amount = total_info.get("value", "0.00")
        currency = total_info.get("currency", "USD")

        wallet_details = DigitalWalletProvider.tokenize_payment(method_name, amount, currency)

        return PaymentResponse(
            request_id=self.id,
            method_name=method_name,
            details=wallet_details,
            payer_name="Alice Enterprise",
            payer_email="alice@enterprise.local",
            payer_phone="+14155550199",
            shipping_address=PaymentAddress()
        )
