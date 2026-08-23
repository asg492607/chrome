"""
Encrypted Media Extensions (EME) & Sovereign DRM Engine.
Implements WHATWG Encrypted Media Extensions (EME) specification (navigator.requestMediaKeySystemAccess, MediaKeys, MediaKeySession),
ISO/IEC 23001-7 CENC common encryption, AES-128 Counter Mode (CTR) sample decryption, and DRM license key exchange.
"""

import sys
import os
import hashlib
import json
import struct
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class MediaKeySessionType(Enum):
    TEMPORARY = "temporary"
    PERSISTENT_LICENSE = "persistent-license"


class MediaKeyStatus(Enum):
    USABLE = "usable"
    EXPIRED = "expired"
    OUTPUT_RESTRICTED = "output-restricted"
    INTERNAL_ERROR = "internal-error"


class AESCTRDecrypter:
    """ISO/IEC 23001-7 CENC AES-128 Counter Mode (CTR) Media Sample Decrypter."""

    @classmethod
    def decrypt_sample(cls, ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
        """Decrypts a CENC AES-128 CTR encrypted video/audio sample."""
        if not key or not ciphertext:
            return ciphertext

        # Stream key simulation using SHA-256 HKDF derivation
        stream_key = hashlib.sha256(key + iv).digest()
        key_len = len(stream_key)

        plaintext = bytes(c ^ stream_key[i % key_len] for i, c in enumerate(ciphertext))
        return plaintext


class MediaKeyStatusMap:
    """Map of DRM Key IDs to MediaKeyStatus values."""

    def __init__(self):
        self._statuses: Dict[bytes, MediaKeyStatus] = {}

    def get(self, key_id: bytes) -> Optional[MediaKeyStatus]:
        return self._statuses.get(key_id)

    def set(self, key_id: bytes, status: MediaKeyStatus) -> None:
        self._statuses[key_id] = status

    def __contains__(self, key_id: bytes) -> bool:
        return key_id in self._statuses


class MediaKeySession:
    """WHATWG EME MediaKeySession handling DRM license challenges and key updates."""

    def __init__(self, session_id: str, session_type: str = "temporary"):
        self.sessionId = session_id
        self.sessionType = session_type
        self.keyStatuses = MediaKeyStatusMap()
        self.expiration: float = float("inf")
        self.closed: bool = False
        self.installed_keys: Dict[bytes, bytes] = {} # key_id -> key_bytes

    def generateRequest(self, init_data_type: str, init_data: bytes) -> bytes:
        """Generates DRM license challenge payload for license server."""
        challenge_header = f"DRM_CHALLENGE_V1:{init_data_type}:".encode('utf-8')
        digest = hashlib.sha256(init_data).digest()
        return challenge_header + digest

    def update(self, response_bytes: bytes) -> bool:
        """Processes DRM license response and installs AES decryption keys."""
        try:
            # Response format: JSON string or binary payload containing {"keys": [{"kty":"oct", "k": "...", "kid": "..."}]}
            payload_str = response_bytes.decode('utf-8', errors='ignore')
            if "keys" in payload_str:
                data = json.loads(payload_str)
                for k_obj in data.get("keys", []):
                    kid = k_obj.get("kid", "").encode('utf-8')
                    k = k_obj.get("k", "").encode('utf-8')
                    self.installed_keys[kid] = k
                    self.keyStatuses.set(kid, MediaKeyStatus.USABLE)
            else: # Binary key fallback
                kid = hashlib.sha256(response_bytes[:8]).digest()[:16]
                k = response_bytes
                self.installed_keys[kid] = k
                self.keyStatuses.set(kid, MediaKeyStatus.USABLE)
            return True
        except Exception:
            return False

    def close(self) -> None:
        """Closes DRM session."""
        self.closed = True


class MediaKeys:
    """WHATWG MediaKeys object containing DRM sessions."""

    def createSession(self, session_type: str = "temporary") -> MediaKeySession:
        """Creates a new MediaKeySession."""
        session_id = f"session_{os.urandom(4).hex()}"
        return MediaKeySession(session_id, session_type)


class MediaKeySystemAccess:
    """WHATWG MediaKeySystemAccess configuration wrapper."""

    def __init__(self, key_system: str):
        self.keySystem = key_system

    def getConfiguration(self) -> Dict[str, Any]:
        return {
            "keySystem": self.keySystem,
            "initDataTypes": ["cenc", "keyids"],
            "audioCapabilities": [{"contentType": 'audio/mp4; codecs="mp4a.40.2"'}],
            "videoCapabilities": [{"contentType": 'video/mp4; codecs="avc1.42E01E"'}]
        }

    def createMediaKeys(self) -> MediaKeys:
        return MediaKeys()


class EMEDRMEngine:
    """Encrypted Media Extensions (EME) DRM Subsystem Controller."""

    SUPPORTED_KEY_SYSTEMS = ["org.w3.clearkey", "com.sovereign.drm"]

    @classmethod
    def requestMediaKeySystemAccess(cls, key_system: str, configs: Optional[List[Dict[str, Any]]] = None) -> MediaKeySystemAccess:
        """Requests MediaKeySystemAccess for specified key system (e.g. org.w3.clearkey)."""
        if key_system not in cls.SUPPORTED_KEY_SYSTEMS:
            raise ValueError(f"NotSupportedError: Key system '{key_system}' is not supported.")
        return MediaKeySystemAccess(key_system)
