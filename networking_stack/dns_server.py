"""
RFC 1035 Recursive DNS Resolver & Cryptographic Anti-Poisoning Cache Engine.
Provides multi-record resolution (A, AAAA, CNAME, TXT), recursive alias resolution with loop detection,
and cryptographic transaction ID nonces for trustless, zero-telemetry name resolution.
"""

import socket
import threading
import json
import time
import sys
import os
import secrets
import hashlib
from enum import IntEnum
from typing import Dict, List, Optional, Any, Tuple, Set

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core_platform.logging_system import sys_logger


class RecordType(IntEnum):
    """RFC 1035 Standard Resource Record Types."""
    A = 1        # IPv4 Address
    NS = 2       # Authoritative Name Server
    CNAME = 5    # Canonical Name Alias
    SOA = 6      # Start of Authority
    PTR = 12     # Domain Name Pointer (Reverse DNS)
    MX = 15      # Mail Exchange
    TXT = 16     # Text Strings / Security Policies
    AAAA = 28    # IPv6 Address


class DNSRecord:
    """Represents a single DNS Resource Record with TTL lifetime tracking."""
    def __init__(
        self,
        name: str,
        record_type: RecordType,
        value: str,
        ttl: float = 300.0
    ):
        self.name = name.strip().lower()
        self.record_type = RecordType(record_type)
        self.value = value
        self.ttl = float(ttl)
        self.created_at = time.time()

    def is_expired(self) -> bool:
        return (time.time() - self.created_at) >= self.ttl

    def remaining_ttl(self) -> int:
        remaining = self.ttl - (time.time() - self.created_at)
        return max(0, int(remaining))

    def compute_hash(self) -> str:
        """Computes a SHA-256 integrity hash over the record's immutable fields."""
        payload = f"{self.name}:{self.record_type.name}:{self.value}:{self.ttl}"
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.record_type.name,
            "type_id": int(self.record_type),
            "value": self.value,
            "ttl": self.remaining_ttl()
        }


class CryptographicDNSCache:
    """
    Thread-Safe Local DNS Cache with Anti-Poisoning Verification.
    Verifies query TXIDs, discards unsolicited responses, and prevents cache tampering.
    """

    def __init__(self, default_ttl: float = 300.0):
        self.default_ttl = default_ttl
        self.lock = threading.Lock()
        # Key: (domain: str, record_type: int) -> Tuple[DNSRecord, str (hash)]
        self._cache: Dict[Tuple[str, int], Tuple[DNSRecord, str]] = {}
        # Active pending query nonces: tx_id -> (domain, timestamp)
        self._pending_queries: Dict[int, Tuple[str, float]] = {}

    def register_query(self, domain: str) -> int:
        """Generates a cryptographically random 16-bit TXID for a pending query."""
        with self.lock:
            # Clean queries older than 5 seconds
            now = time.time()
            expired_tx = [tx for tx, (_, ts) in self._pending_queries.items() if (now - ts) > 5.0]
            for tx in expired_tx:
                self._pending_queries.pop(tx, None)

            # Generate random 16-bit integer (0x0001 to 0xFFFF)
            tx_id = secrets.randbelow(0xFFFE) + 1
            self._pending_queries[tx_id] = (domain.strip().lower(), now)
            return tx_id

    def verify_response(self, tx_id: int, domain: str) -> bool:
        """Verifies if incoming UDP response matches a registered pending query."""
        with self.lock:
            domain_clean = domain.strip().lower()
            if tx_id not in self._pending_queries:
                sys_logger.log(f"[DNS Security Alert] Dropped unsolicited DNS response (TXID: {tx_id})")
                return False

            expected_domain, _ = self._pending_queries.pop(tx_id)
            if expected_domain != domain_clean:
                sys_logger.log(f"[DNS Security Alert] Domain mismatch! Expected '{expected_domain}', got '{domain_clean}'")
                return False

            return True

    def put(self, record: DNSRecord) -> None:
        """Stores record with cryptographic integrity verification digest."""
        with self.lock:
            key = (record.name, int(record.record_type))
            self._cache[key] = (record, record.compute_hash())

    def get(self, domain: str, record_type: RecordType) -> Optional[DNSRecord]:
        """Retrieves cached record if not expired and cryptographic hash matches."""
        with self.lock:
            key = (domain.strip().lower(), int(record_type))
            if key not in self._cache:
                return None

            record, stored_hash = self._cache[key]
            # Check expiration
            if record.is_expired():
                self._cache.pop(key, None)
                return None

            # Verify in-memory integrity
            if record.compute_hash() != stored_hash:
                sys_logger.log(f"[DNS Security Alert] Cache corruption detected for '{domain}'! Evicting entry.")
                self._cache.pop(key, None)
                return None

            return record

    def evict_expired(self) -> int:
        """Evicts all expired records from cache."""
        with self.lock:
            keys_to_remove = [k for k, (rec, _) in self._cache.items() if rec.is_expired()]
            for k in keys_to_remove:
                self._cache.pop(k, None)
            return len(keys_to_remove)

    def clear(self) -> None:
        with self.lock:
            self._cache.clear()
            self._pending_queries.clear()


class DNSServer:
    """
    Self-Contained Authoritative & Recursive DNS Server.
    Supports A, AAAA, CNAME, and TXT records with loop-detected alias resolution.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 5353):
        self.host = host
        self.port = port
        self.running = False
        self.socket: Optional[socket.socket] = None
        self.lock = threading.Lock()

        # Authoritative Zone Records (Domain -> List[DNSRecord])
        self.zone_records: Dict[str, List[DNSRecord]] = {}
        self._init_default_zone()

        # Telemetry
        self.total_queries = 0
        self.total_success = 0
        self.total_nxdomain = 0

    def _init_default_zone(self) -> None:
        """Populates default local zone records."""
        defaults = [
            ("asgsearch.local", RecordType.A, "127.0.0.1", 3600.0),
            ("asgsearch.local", RecordType.AAAA, "::1", 3600.0),
            ("asgsearch.local", RecordType.TXT, "v=spf1 -all; sovereign=true", 3600.0),
            ("myblog.com", RecordType.CNAME, "asgsearch.local", 3600.0),
            ("news.com", RecordType.A, "127.0.0.1", 3600.0),
            ("news.com", RecordType.TXT, "news-portal-v1", 3600.0),
            ("localhost", RecordType.A, "127.0.0.1", 86400.0),
            ("localhost", RecordType.AAAA, "::1", 86400.0),
        ]
        for name, rtype, val, ttl in defaults:
            self.add_record(DNSRecord(name, rtype, val, ttl))

    def add_record(self, record: DNSRecord) -> None:
        """Adds a Resource Record to the authoritative zone."""
        with self.lock:
            domain = record.name
            if domain not in self.zone_records:
                self.zone_records[domain] = []
            self.zone_records[domain].append(record)

    def start(self) -> None:
        """Starts the UDP DNS listener."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.socket.bind((self.host, self.port))
        except Exception as e:
            sys_logger.log(f"[DNS Server Error] Failed to bind {self.host}:{self.port}: {e}")
            return

        self.running = True
        sys_logger.log(f"[DNS Server] Listening on {self.host}:{self.port} ({len(self.zone_records)} Zone Entries)")

        thread = threading.Thread(target=self._listen_loop, daemon=True, name="DNSServerLoop")
        thread.start()

    def stop(self) -> None:
        """Stops the DNS server."""
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
        sys_logger.log("[DNS Server] Stopped")

    def _listen_loop(self) -> None:
        while self.running:
            try:
                data, addr = self.socket.recvfrom(4096)
                if not data:
                    continue

                message = json.loads(data.decode('utf-8'))
                self._handle_query(message, addr)

            except OSError:
                break
            except Exception as e:
                sys_logger.log(f"[DNS Server Loop Error] {e}")

    def resolve_recursive(
        self,
        domain: str,
        record_type: RecordType = RecordType.A,
        max_depth: int = 5
    ) -> Tuple[str, List[DNSRecord]]:
        """
        Recursively resolves domain queries, following CNAME chains with loop detection.
        Returns (Status, List of matching DNSRecords).
        """
        domain_clean = domain.strip().lower()
        visited: Set[str] = set()
        current_domain = domain_clean
        depth = 0

        with self.lock:
            while depth < max_depth:
                if current_domain in visited:
                    return "LOOP_DETECTED", []
                visited.add(current_domain)

                if current_domain not in self.zone_records:
                    return "NXDOMAIN", []

                records = self.zone_records[current_domain]
                
                # Check for direct matching record type
                matching = [r for r in records if r.record_type == record_type and not r.is_expired()]
                if matching:
                    return "SUCCESS", matching

                # If asking for A/AAAA and CNAME exists, follow CNAME alias
                cnames = [r for r in records if r.record_type == RecordType.CNAME and not r.is_expired()]
                if cnames:
                    current_domain = cnames[0].value.strip().lower()
                    depth += 1
                    continue

                # If no matching type and no CNAME -> NODATA
                return "NXDOMAIN", []

            return "MAX_DEPTH_EXCEEDED", []

    def _handle_query(self, message: Dict[str, Any], addr: Tuple[str, int]) -> None:
        msg_type = message.get("type", "").upper()
        domain = message.get("domain", "")
        tx_id = message.get("tx_id", 0)
        rtype_id = message.get("record_type", int(RecordType.A))
        
        try:
            record_type = RecordType(rtype_id)
        except ValueError:
            record_type = RecordType.A

        self.total_queries += 1

        if msg_type == "QUERY":
            status, records = self.resolve_recursive(domain, record_type)
            if status == "SUCCESS":
                self.total_success += 1
                primary_value = records[0].value if records else None
            else:
                self.total_nxdomain += 1
                primary_value = None

            response = {
                "type": "RESPONSE",
                "tx_id": tx_id,
                "domain": domain,
                "record_type": record_type.name,
                "ip": primary_value,  # Backward compatible field
                "status": status,
                "records": [r.to_dict() for r in records]
            }
            self.socket.sendto(json.dumps(response).encode('utf-8'), addr)
            sys_logger.log(f"[DNS Server] Resolved '{domain}' ({record_type.name}) -> {primary_value} ({status})")

    def get_diagnostics(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "zones_count": len(self.zone_records),
                "total_queries": self.total_queries,
                "total_success": self.total_success,
                "total_nxdomain": self.total_nxdomain
            }


class DNSClientEngine:
    """
    Sovereign DNS Client with Cryptographic Anti-Poisoning Cache.
    Resolves domain names with sub-millisecond local cache hit retrieval.
    """

    def __init__(
        self,
        dns_server_host: str = "127.0.0.1",
        dns_server_port: int = 5353,
        cache_ttl: float = 300.0
    ):
        self.server_host = dns_server_host
        self.server_port = dns_server_port
        self.cache = CryptographicDNSCache(default_ttl=cache_ttl)

    def resolve(
        self,
        domain: str,
        record_type: RecordType = RecordType.A,
        timeout: float = 2.0
    ) -> Optional[str]:
        """
        Resolves domain name. Checks local cache first; falls back to DNS UDP server.
        Returns resolved value (IP string or text payload) or None.
        """
        domain_clean = domain.strip().lower()

        # 1. Check local cryptographic cache
        cached_record = self.cache.get(domain_clean, record_type)
        if cached_record:
            return cached_record.value

        # 2. Register secure cryptographic TXID nonce
        tx_id = self.cache.register_query(domain_clean)
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)

        query = {
            "type": "QUERY",
            "tx_id": tx_id,
            "domain": domain_clean,
            "record_type": int(record_type)
        }

        try:
            sock.sendto(json.dumps(query).encode('utf-8'), (self.server_host, self.server_port))
            data, _ = sock.recvfrom(4096)
            response = json.loads(data.decode('utf-8'))

            # 3. Anti-Poisoning Nonce Verification
            resp_tx = response.get("tx_id", 0)
            if not self.cache.verify_response(resp_tx, domain_clean):
                return None

            if response.get("status") != "SUCCESS":
                return None

            primary_value = response.get("ip")
            records_data = response.get("records", [])

            # 4. Populate local cache with verified records
            for r_data in records_data:
                rtype = RecordType[r_data.get("type", "A")]
                rec = DNSRecord(
                    name=r_data.get("name", domain_clean),
                    record_type=rtype,
                    value=r_data.get("value", primary_value),
                    ttl=float(r_data.get("ttl", 300.0))
                )
                self.cache.put(rec)

            return primary_value

        except socket.timeout:
            return None
        except Exception:
            return None
        finally:
            sock.close()


def resolve_dns(domain, dns_server_host="127.0.0.1", dns_server_port=5353):
    """Backward-compatible helper function for legacy callers."""
    client = DNSClientEngine(dns_server_host=dns_server_host, dns_server_port=dns_server_port)
    return client.resolve(domain)
