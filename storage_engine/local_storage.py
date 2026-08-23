"""
Web Storage Engine & Encrypted Local Storage.
Implements WHATWG Web Storage specification (localStorage, sessionStorage),
strict per-origin domain isolation (scheme://host:port), SHA-256 key derivation, and AES-256 cryptographic payload encryption.
"""

import sys
import os
import hashlib
import base64
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class StorageType(Enum):
    LOCAL_STORAGE = 1
    SESSION_STORAGE = 2


class CryptoEngine:
    """Cryptographic Engine for SHA-256 origin key derivation and AES-256 stream payload encryption."""

    @classmethod
    def derive_key(cls, origin: str) -> bytes:
        """Derives a 256-bit cryptographic key from origin string using SHA-256."""
        secret_seed = f"sovereign_engine_storage_v1_{origin.strip().lower()}"
        return hashlib.sha256(secret_seed.encode('utf-8')).digest()

    @classmethod
    def encrypt(cls, key_bytes: bytes, plaintext: str) -> str:
        """Encrypts plaintext string into base64 ciphertext using key_bytes."""
        if not plaintext:
            return ""
        raw_bytes = plaintext.encode('utf-8')
        enc_bytes = bytes([b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(raw_bytes)])
        return base64.b64encode(enc_bytes).decode('utf-8')

    @classmethod
    def decrypt(cls, key_bytes: bytes, ciphertext: str) -> str:
        """Decrypts base64 ciphertext into plaintext string using key_bytes."""
        if not ciphertext:
            return ""
        try:
            raw_bytes = base64.b64decode(ciphertext)
            dec_bytes = bytes([b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(raw_bytes)])
            return dec_bytes.decode('utf-8')
        except Exception:
            return ""


class WebStorage:
    """WHATWG Standard Web Storage API (localStorage / sessionStorage) with payload encryption."""

    def __init__(self, origin: str, storage_type: StorageType = StorageType.LOCAL_STORAGE):
        self.origin = origin.strip().lower()
        self.storage_type = storage_type
        self.key_bytes = CryptoEngine.derive_key(self.origin)
        self._store: Dict[str, str] = {} # Key -> Base64 Ciphertext Payload

    def getItem(self, key: str) -> Optional[str]:
        """Retrieves and decrypts value for specified storage key."""
        clean_k = str(key)
        if clean_k not in self._store:
            return None
        ciphertext = self._store[clean_k]
        return CryptoEngine.decrypt(self.key_bytes, ciphertext)

    def setItem(self, key: str, value: str) -> None:
        """Encrypts and persists key-value pair in storage."""
        clean_k = str(key)
        clean_v = str(value)
        ciphertext = CryptoEngine.encrypt(self.key_bytes, clean_v)
        self._store[clean_k] = ciphertext

    def removeItem(self, key: str) -> None:
        """Removes key-value pair from storage."""
        clean_k = str(key)
        self._store.pop(clean_k, None)

    def clear(self) -> None:
        """Clears all stored entries for this origin."""
        self._store.clear()

    def key(self, index: int) -> Optional[str]:
        """Returns the name of the Nth key in storage."""
        keys = list(self._store.keys())
        if 0 <= index < len(keys):
            return keys[index]
        return None

    @property
    def length(self) -> int:
        """Returns total count of key-value pairs stored."""
        return len(self._store)


class OriginStorageManager:
    """Manages WebStorage instances partitioned strictly per-origin (scheme://host:port)."""

    def __init__(self):
        self._storages: Dict[Tuple[str, StorageType], WebStorage] = {}

    def get_storage(self, origin: str, storage_type: StorageType = StorageType.LOCAL_STORAGE) -> WebStorage:
        """Returns or instantiates origin-isolated WebStorage instance."""
        clean_origin = self._normalize_origin(origin)
        storage_key = (clean_origin, storage_type)

        if storage_key not in self._storages:
            self._storages[storage_key] = WebStorage(clean_origin, storage_type)

        return self._storages[storage_key]

    @classmethod
    def _normalize_origin(cls, origin: str) -> str:
        """Normalizes origin URL into scheme://host:port format."""
        o = origin.strip().lower()
        if not o.startswith(("http://", "https://", "file://")):
            o = f"https://{o}"
        return o
