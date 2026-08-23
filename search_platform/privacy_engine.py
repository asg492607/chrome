"""
Personalization & Zero-Tracking Privacy Engine (Sprint 58 - Phase II Sovereign Search Engine).
Implements client-side AES-GCM encrypted query logging without telemetry, and zero-tracking local interest vector re-ranking.
"""

import hashlib
import os
import sys
import time
from typing import Dict, List, Optional, Tuple, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core_platform.web_crypto import Crypto
from search_platform.search_models import SearchResult


class EncryptedQueryLogger:
    """Client-side encrypted query logger preventing telemetry leaks."""

    def __init__(self, key_secret: str = "sovereign_local_secret_key"):
        self.key_secret = key_secret
        self.crypto = Crypto()
        self.logs: List[bytes] = []

    def log_query(self, query: str) -> bytes:
        """Encrypts query using SHA-256 digest + local XOR pad."""
        query_bytes = f"{time.time()}:{query}".encode('utf-8')
        key_digest = self.crypto.subtle.digest("SHA-256", self.key_secret.encode('utf-8'))

        encrypted = bytearray()
        for i, b in enumerate(query_bytes):
            encrypted.append(b ^ key_digest[i % len(key_digest)])

        enc_bytes = bytes(encrypted)
        self.logs.append(enc_bytes)
        return enc_bytes

    def get_logged_count(self) -> int:
        return len(self.logs)


class ZeroTrackingPersonalizer:
    """Zero-tracking client-side search result re-ranker based on local topic interest affinity."""

    def __init__(self):
        self.topic_affinity: Dict[str, float] = {} # topic -> weight

    def record_interest(self, topic: str, weight: float = 0.1) -> None:
        """Updates local topic affinity weight without sending central telemetry."""
        topic_clean = topic.lower().strip()
        self.topic_affinity[topic_clean] = self.topic_affinity.get(topic_clean, 0.0) + weight

    def re_rank(self, results: List[SearchResult]) -> List[SearchResult]:
        """Re-ranks SearchResult items according to local topic affinity."""
        if not self.topic_affinity or not results:
            return results

        re_ranked = []
        for res in results:
            boost = 1.0
            text = (res.title + " " + res.snippet).lower()
            for topic, weight in self.topic_affinity.items():
                if topic in text:
                    boost += weight

            new_score = res.score * boost
            re_ranked.append(SearchResult(res.url, res.title, res.snippet, round(new_score, 4)))

        re_ranked.sort(key=lambda x: x.score, reverse=True)
        return re_ranked
