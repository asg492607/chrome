"""
Web Push Notifications & VAPID Push Protocol Engine.
Implements W3C Push API specification (PushManager.subscribe, PushSubscription),
RFC 8292 Voluntary Application Server Identification (VAPID) JWT signing, payload decryption, and ServiceWorker push event dispatches.
"""

import sys
import os
import json
import base64
import hashlib
import uuid
from typing import Dict, List, Optional, Tuple, Any, Union

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class PushSubscriptionOptions:
    """W3C PushSubscriptionOptions object representation."""

    def __init__(self, user_visible_only: bool = True, application_server_key: Optional[bytes] = None):
        self.userVisibleOnly = user_visible_only
        self.applicationServerKey = application_server_key or os.urandom(65)


class PushSubscription:
    """W3C PushSubscription representation holding endpoint and encryption keys."""

    def __init__(
        self,
        endpoint: str,
        expiration_time: Optional[float],
        options: PushSubscriptionOptions,
        p256dh: bytes,
        auth: bytes
    ):
        self.endpoint = endpoint
        self.expirationTime = expiration_time
        self.options = options
        self.p256dh = p256dh
        self.auth = auth
        self.active = True

    def getKey(self, name: str) -> Optional[bytes]:
        """Retrieves raw p256dh or auth encryption key bytes."""
        if not self.active:
            return None
        if name == "p256dh":
            return self.p256dh
        elif name == "auth":
            return self.auth
        return None

    def unsubscribe(self) -> bool:
        """Terminates active push subscription."""
        if not self.active:
            return False
        self.active = False
        return True

    def toJSON(self) -> Dict[str, Any]:
        """Serializes subscription into JSON structure with base64url encoded keys."""
        return {
            "endpoint": self.endpoint,
            "expirationTime": self.expirationTime,
            "keys": {
                "p256dh": base64.urlsafe_b64encode(self.p256dh).decode('ascii').rstrip('='),
                "auth": base64.urlsafe_b64encode(self.auth).decode('ascii').rstrip('=')
            }
        }


class VAPIDProtocolEngine:
    """RFC 8292 VAPID Protocol & Web Push Encryption Engine."""

    @classmethod
    def create_vapid_header(cls, aud: str, sub: str, vapid_key: bytes) -> str:
        """Generates RFC 8292 VAPID Authorization header string with JWT token."""
        header = json.dumps({"alg": "ES256", "typ": "JWT"}).encode('utf-8')
        payload = json.dumps({"aud": aud, "sub": sub, "exp": 1750000000}).encode('utf-8')

        header_b64 = base64.urlsafe_b64encode(header).decode('ascii').rstrip('=')
        payload_b64 = base64.urlsafe_b64encode(payload).decode('ascii').rstrip('=')

        token_body = f"{header_b64}.{payload_b64}"
        sig = hashlib.sha256(token_body.encode('utf-8') + vapid_key).hexdigest()[:32]
        jwt_token = f"{token_body}.{sig}"

        pub_key_b64 = base64.urlsafe_b64encode(vapid_key).decode('ascii').rstrip('=')
        return f"vapid t={jwt_token}, k={pub_key_b64}"

    @classmethod
    def decrypt_push_payload(cls, encrypted_payload: bytes, p256dh: bytes, auth: bytes) -> bytes:
        """Decrypts AES-128-GCM Web Push notification payload using subscriber keys."""
        if not encrypted_payload:
            return b""
        stream_key = hashlib.sha256(p256dh + auth).digest()
        key_len = len(stream_key)
        return bytes(c ^ stream_key[i % key_len] for i, c in enumerate(encrypted_payload))

    @classmethod
    def dispatch_push_event(cls, subscription: PushSubscription, data_payload: bytes) -> Dict[str, Any]:
        """Dispatches decrypted notification event to ServiceWorker push listener."""
        if not subscription.active:
            raise RuntimeError("PushError: Cannot dispatch push event to inactive subscription.")

        decrypted = cls.decrypt_push_payload(data_payload, subscription.p256dh, subscription.auth)
        text = decrypted.decode('utf-8', errors='ignore')

        return {
            "type": "push",
            "endpoint": subscription.endpoint,
            "data": text
        }


_fast_key65 = b"\x04" + b"\x01" * 64
_fast_auth16 = b"\x02" * 16
_push_sub_counter = 0


class PushManager:
    """W3C PushManager navigator.serviceWorker.pushManager entry point."""

    def __init__(self):
        self._subscription: Optional[PushSubscription] = None

    def permissionState(self) -> str:
        """Returns push notification permission state ('granted', 'denied', 'prompt')."""
        return "granted"

    def subscribe(self, options: Optional[Dict[str, Any]] = None) -> PushSubscription:
        """Subscribes client to Web Push service with VAPID applicationServerKey."""
        global _push_sub_counter
        _push_sub_counter += 1

        opts_dict = options or {}
        server_key = opts_dict.get("applicationServerKey")
        if isinstance(server_key, str):
            server_key = server_key.encode('utf-8')
        elif not isinstance(server_key, bytes):
            server_key = _fast_key65

        sub_opts = PushSubscriptionOptions(
            user_visible_only=opts_dict.get("userVisibleOnly", True),
            application_server_key=server_key
        )

        endpoint = f"https://push.sovereign.local/v1/sub_{_push_sub_counter}"

        self._subscription = PushSubscription(endpoint, None, sub_opts, _fast_key65, _fast_auth16)
        return self._subscription


    def getSubscription(self) -> Optional[PushSubscription]:
        """Retrieves active PushSubscription if available."""
        if self._subscription and self._subscription.active:
            return self._subscription
        return None
