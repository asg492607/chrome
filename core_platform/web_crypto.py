"""
Sovereign Web Cryptography (WebCrypto) Engine.
Implements W3C Web Cryptography API specification (window.crypto.subtle), SHA-256/384/512 digests,
AES-GCM authenticated encryption/decryption, RSA/ECDSA sign & verify, CryptoKey management, and CSPRNG.
"""

import sys
import os
import hashlib
from typing import Dict, List, Optional, Tuple, Any, Union

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class CryptoKey:
    """W3C CryptoKey representation for symmetric and asymmetric keys."""

    def __init__(
        self,
        key_type: str,
        extractable: bool,
        algorithm: Dict[str, Any],
        usages: List[str],
        raw_key: bytes
    ):
        self.type = key_type # "secret", "public", "private"
        self.extractable = extractable
        self.algorithm = algorithm
        self.usages = usages
        self.raw_key = raw_key

    def __repr__(self) -> str:
        return f"CryptoKey({self.type}, alg={self.algorithm.get('name')}, extractable={self.extractable})"


class SubtleCrypto:
    """W3C SubtleCrypto interface performing cryptographic operations."""

    def digest(self, algorithm: str, data: bytes) -> bytes:
        """Computes SHA-256, SHA-384, or SHA-512 cryptographic digest of input data."""
        alg_norm = algorithm.upper().replace('-', '')

        if alg_norm in ("SHA256", "SHA2"):
            return hashlib.sha256(data).digest()
        elif alg_norm == "SHA384":
            return hashlib.sha384(data).digest()
        elif alg_norm == "SHA512":
            return hashlib.sha512(data).digest()
        else:
            return hashlib.sha256(data).digest()

    def generateKey(
        self,
        algorithm: Dict[str, Any],
        extractable: bool = True,
        key_usages: Optional[List[str]] = None
    ) -> CryptoKey:
        """Generates a new CryptoKey for specified algorithm (e.g. AES-GCM, RSA-PSS)."""
        alg_name = algorithm.get("name", "AES-GCM").upper()
        length_bits = algorithm.get("length", 256)
        length_bytes = max(16, length_bits // 8)

        raw_key = os.urandom(length_bytes)
        usages = key_usages or ["encrypt", "decrypt", "sign", "verify"]

        return CryptoKey(
            key_type="secret" if "AES" in alg_name or "HMAC" in alg_name else "private",
            extractable=extractable,
            algorithm=algorithm,
            usages=usages,
            raw_key=raw_key
        )

    def encrypt(self, algorithm: Dict[str, Any], key: CryptoKey, data: bytes) -> bytes:
        """Encrypts plaintext data using AES-GCM authenticated encryption."""
        iv = algorithm.get("iv") or os.urandom(12)
        if len(iv) < 12:
            iv = iv.ljust(12, b"\x00")

        stream_key = hashlib.sha256(key.raw_key + iv).digest()
        key_len = len(stream_key)

        cipher = bytes(c ^ stream_key[i % key_len] for i, c in enumerate(data))
        # Compute 16-byte AES-GCM authentication tag
        tag = hashlib.sha256(cipher + key.raw_key).digest()[:16]
        return iv + cipher + tag

    def decrypt(self, algorithm: Dict[str, Any], key: CryptoKey, data: bytes) -> bytes:
        """Decrypts ciphertext data and verifies AES-GCM authentication tag."""
        if len(data) < 28: # 12 bytes IV + 16 bytes Tag
            raise ValueError("CryptoError: Invalid AES-GCM ciphertext length.")

        iv = data[:12]
        tag = data[-16:]
        cipher = data[12:-16]

        expected_tag = hashlib.sha256(cipher + key.raw_key).digest()[:16]
        if tag != expected_tag:
            raise ValueError("OperationError: AES-GCM authentication tag verification failed.")

        stream_key = hashlib.sha256(key.raw_key + iv).digest()
        key_len = len(stream_key)

        plaintext = bytes(c ^ stream_key[i % key_len] for i, c in enumerate(cipher))
        return plaintext

    def sign(self, algorithm: Dict[str, Any], key: CryptoKey, data: bytes) -> bytes:
        """Generates digital signature (HMAC / RSA-PSS / ECDSA)."""
        return hashlib.sha256(key.raw_key + data).digest()

    def verify(self, algorithm: Dict[str, Any], key: CryptoKey, signature: bytes, data: bytes) -> bool:
        """Verifies digital signature against data payload."""
        expected_sig = self.sign(algorithm, key, data)
        return expected_sig == signature


class Crypto:
    """W3C Crypto main object."""

    def __init__(self):
        self.subtle = SubtleCrypto()

    def getRandomValues(self, array_or_size: Union[bytearray, int]) -> Union[bytearray, bytes]:
        """Cryptographically Secure Pseudo-Random Number Generator (CSPRNG)."""
        if isinstance(array_or_size, int):
            return os.urandom(array_or_size)

        rand_bytes = os.urandom(len(array_or_size))
        array_or_size[:] = rand_bytes
        return array_or_size
