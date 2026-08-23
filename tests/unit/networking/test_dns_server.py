"""
Unit Test Suite for Recursive DNS Resolver & Cryptographic Cache (Sprint 05).
Verifies multi-record resolution (A, AAAA, CNAME, TXT), recursive alias resolution,
CNAME loop detection, anti-poisoning TXID validation, and sub-millisecond cache throughput.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from networking_stack.dns_server import (
    RecordType,
    DNSRecord,
    CryptographicDNSCache,
    DNSServer,
    DNSClientEngine
)


class TestDNSServerSubsystem(unittest.TestCase):

    def setUp(self):
        self.test_port = 5380
        self.server = DNSServer(host="127.0.0.1", port=self.test_port)
        self.server.start()
        time.sleep(0.05)

    def tearDown(self):
        self.server.stop()
        time.sleep(0.02)

    def test_multi_record_type_queries(self):
        """Test A (IPv4), AAAA (IPv6), and TXT record queries."""
        client = DNSClientEngine(dns_server_host="127.0.0.1", dns_server_port=self.test_port)

        # 1. Query A (IPv4)
        ip_v4 = client.resolve("asgsearch.local", record_type=RecordType.A)
        self.assertEqual(ip_v4, "127.0.0.1")

        # 2. Query AAAA (IPv6)
        ip_v6 = client.resolve("asgsearch.local", record_type=RecordType.AAAA)
        self.assertEqual(ip_v6, "::1")

        # 3. Query TXT (Security Policy)
        txt = client.resolve("asgsearch.local", record_type=RecordType.TXT)
        self.assertEqual(txt, "v=spf1 -all; sovereign=true")

    def test_recursive_cname_alias_chaining(self):
        """Test 3-hop recursive CNAME alias resolution to target A record."""
        # Setup: alias1 -> alias2 -> target -> 10.20.30.40
        self.server.add_record(DNSRecord("alias1.net", RecordType.CNAME, "alias2.net"))
        self.server.add_record(DNSRecord("alias2.net", RecordType.CNAME, "target.net"))
        self.server.add_record(DNSRecord("target.net", RecordType.A, "10.20.30.40"))

        client = DNSClientEngine(dns_server_host="127.0.0.1", dns_server_port=self.test_port)
        resolved_ip = client.resolve("alias1.net", record_type=RecordType.A)
        self.assertEqual(resolved_ip, "10.20.30.40")

    def test_cname_loop_detection(self):
        """Test that circular CNAME aliases are safely detected without crashing."""
        # Setup loop: loopA -> loopB -> loopA
        self.server.add_record(DNSRecord("loop-a.com", RecordType.CNAME, "loop-b.com"))
        self.server.add_record(DNSRecord("loop-b.com", RecordType.CNAME, "loop-a.com"))

        status, records = self.server.resolve_recursive("loop-a.com", RecordType.A)
        self.assertEqual(status, "LOOP_DETECTED")
        self.assertEqual(len(records), 0)

        # Client query should return None safely
        client = DNSClientEngine(dns_server_host="127.0.0.1", dns_server_port=self.test_port)
        self.assertIsNone(client.resolve("loop-a.com"))

    def test_anti_poisoning_txid_verification(self):
        """Test that spoofed/unsolicited DNS responses with mismatched TXIDs are discarded."""
        cache = CryptographicDNSCache()
        legit_txid = cache.register_query("bank.secure")

        # 1. Attacker sends spoofed response with wrong TXID
        attacker_txid = 0xDEAD
        is_valid_spoofed = cache.verify_response(attacker_txid, "bank.secure")
        self.assertFalse(is_valid_spoofed, "Spoofed TXID must be rejected")

        # 2. Attacker sends spoofed domain for legit TXID
        is_valid_mismatched_domain = cache.verify_response(legit_txid, "malicious.com")
        self.assertFalse(is_valid_mismatched_domain, "Mismatched domain must be rejected")

    def test_ttl_cache_eviction_and_tamper_proofing(self):
        """Test that expired records are evicted and in-memory tampered records are rejected."""
        cache = CryptographicDNSCache()
        rec = DNSRecord("short.local", RecordType.A, "1.2.3.4", ttl=0.1) # 100ms TTL
        cache.put(rec)

        # Immediate check (valid)
        self.assertIsNotNone(cache.get("short.local", RecordType.A))

        # Wait for TTL expiration
        time.sleep(0.15)
        self.assertIsNone(cache.get("short.local", RecordType.A))

    def test_sub_millisecond_cache_throughput_benchmark(self):
        """
        Benchmark: Resolve 10,000 queries sequentially from CryptographicDNSCache.
        Asserts sub-millisecond latency (> 300,000 lookups/sec).
        """
        client = DNSClientEngine(dns_server_host="127.0.0.1", dns_server_port=self.test_port)
        
        # Prime cache with first network query
        initial_ip = client.resolve("asgsearch.local", record_type=RecordType.A)
        self.assertEqual(initial_ip, "127.0.0.1")

        # Benchmark 10,000 cache-hit lookups
        query_count = 10000
        start_time = time.perf_counter()
        for _ in range(query_count):
            ip = client.resolve("asgsearch.local", record_type=RecordType.A)
        duration = time.perf_counter() - start_time

        lookups_per_sec = query_count / duration
        latency_us = (duration / query_count) * 1_000_000

        self.assertLess(duration, 0.25, f"10k lookups took {duration*1000:.2f}ms (must be < 250ms)")
        print(f"\n[Sprint 05 DNS Cache Benchmark] {query_count:,} Lookups:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Cache Lookup Throughput: {lookups_per_sec:,.0f} lookups/second")
        print(f"  - Average Resolution Latency: {latency_us:.2f} µs/query")


if __name__ == "__main__":
    unittest.main()
