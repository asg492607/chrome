"""
Unit Test Suite for Self-Contained DHCP Server & DORA State Machine (Sprint 04).
Verifies DORA handshakes, state transitions, lease timers, automatic reclamation,
DHCPNAK on pool exhaustion, and concurrent zero-collision IP leasing.
"""

import sys
import os
import unittest
import time
import threading

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from networking_stack.dhcp_server import (
    DHCPState,
    DHCPLease,
    DHCPServer,
    DHCPClientEngine
)


class TestDHCPServerSubsystem(unittest.TestCase):

    def setUp(self):
        self.test_port = 6780
        self.server = DHCPServer(
            host="127.0.0.1",
            port=self.test_port,
            ip_start=100,
            ip_end=120,
            default_lease_duration=3600.0
        )
        self.server.start()
        time.sleep(0.05) # Allow socket to bind

    def tearDown(self):
        self.server.stop()
        time.sleep(0.02)

    def test_dora_handshake_and_state_transitions(self):
        """Test complete DISCOVER -> OFFER -> REQUEST -> ACK flow and state machine transitions."""
        client = DHCPClientEngine(
            server_host="127.0.0.1",
            server_port=self.test_port,
            client_id="Agent-Alpha-01",
            mac_addr="00:11:22:33:44:55"
        )
        self.assertEqual(client.state, DHCPState.INIT)

        lease = client.discover_and_request()
        self.assertIsNotNone(lease)
        self.assertEqual(client.state, DHCPState.BOUND)
        self.assertTrue(lease["ip"].startswith("192.168.1."))
        self.assertEqual(lease["router"], "192.168.1.1")
        self.assertEqual(lease["dns"], "192.168.1.53")
        self.assertGreater(lease["lease_time"], 0)

        # Verify server state
        diag = self.server.get_diagnostics()
        self.assertEqual(diag["active_leases_count"], 1)
        self.assertEqual(diag["total_discovers"], 1)
        self.assertEqual(diag["total_offers"], 1)
        self.assertEqual(diag["total_requests"], 1)
        self.assertEqual(diag["total_acks"], 1)

    def test_client_release_and_pool_reclamation(self):
        """Test that DHCPRELEASE immediately frees the IP address for new leases."""
        client = DHCPClientEngine(
            server_host="127.0.0.1",
            server_port=self.test_port,
            client_id="Agent-Release-Test"
        )
        lease = client.discover_and_request()
        leased_ip = lease["ip"]
        self.assertEqual(self.server.get_diagnostics()["active_leases_count"], 1)

        # Release lease
        success = client.release_lease()
        self.assertTrue(success)
        self.assertEqual(client.state, DHCPState.RELEASED)
        self.assertIsNone(client.current_lease)

        time.sleep(0.05)
        # Verify server returned IP to pool
        diag = self.server.get_diagnostics()
        self.assertEqual(diag["active_leases_count"], 0)
        self.assertEqual(diag["total_releases"], 1)
        self.assertIn(leased_ip, self.server.ip_pool)

    def test_lease_expiration_and_timer_reclamation(self):
        """Test timer-based automatic eviction of expired leases."""
        short_server_port = 6781
        short_server = DHCPServer(
            host="127.0.0.1",
            port=short_server_port,
            ip_start=50,
            ip_end=55,
            default_lease_duration=0.2 # 200ms short lease
        )
        short_server.start()
        time.sleep(0.05)

        try:
            client = DHCPClientEngine(
                server_host="127.0.0.1",
                server_port=short_server_port,
                client_id="Agent-Expiring"
            )
            lease = client.discover_and_request()
            self.assertIsNotNone(lease)
            self.assertEqual(short_server.get_diagnostics()["active_leases_count"], 1)

            # Wait for lease expiration
            time.sleep(0.3)
            reclaimed_count = short_server.reclaim_expired_leases()
            self.assertEqual(reclaimed_count, 1)
            self.assertEqual(short_server.get_diagnostics()["active_leases_count"], 0)

        finally:
            short_server.stop()

    def test_pool_exhaustion_and_nak(self):
        """Test that server responds with NAK when IP pool is completely exhausted."""
        tiny_server_port = 6782
        tiny_server = DHCPServer(
            host="127.0.0.1",
            port=tiny_server_port,
            ip_start=200,
            ip_end=201 # Exactly 1 IP available
        )
        tiny_server.start()
        time.sleep(0.05)

        try:
            # Client 1 claims the only IP
            c1 = DHCPClientEngine(server_host="127.0.0.1", server_port=tiny_server_port, client_id="Agent-1")
            l1 = c1.discover_and_request()
            self.assertIsNotNone(l1)

            # Client 2 attempts lease -> should fail / NAK
            c2 = DHCPClientEngine(server_host="127.0.0.1", server_port=tiny_server_port, client_id="Agent-2")
            l2 = c2.discover_and_request(timeout=0.5)
            self.assertIsNone(l2)
            self.assertEqual(c2.state, DHCPState.INIT)
            self.assertEqual(tiny_server.get_diagnostics()["total_naks"], 1)

        finally:
            tiny_server.stop()

    def test_concurrent_client_leases_zero_collision(self):
        """
        Scale Test:
        10 concurrent clients requesting DHCP leases simultaneously.
        Asserts 100% lease acquisition with 0 IP collisions.
        """
        client_count = 10
        clients = [
            DHCPClientEngine(
                server_host="127.0.0.1",
                server_port=self.test_port,
                client_id=f"Concurrent-Agent-{i:02d}",
                mac_addr=f"00:50:56:00:00:{i:02X}"
            )
            for i in range(client_count)
        ]

        leased_ips = []
        lock = threading.Lock()

        def worker(client: DHCPClientEngine):
            lease = client.discover_and_request(timeout=3.0)
            if lease:
                with lock:
                    leased_ips.append(lease["ip"])

        threads = [threading.Thread(target=worker, args=(c,)) for c in clients]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(leased_ips), client_count, f"Expected {client_count} leases, got {len(leased_ips)}")
        
        # Prove 0 collisions (all unique IPs)
        unique_ips = set(leased_ips)
        self.assertEqual(len(unique_ips), client_count, f"IP collision detected! Unique: {len(unique_ips)} vs Total: {client_count}")
        print(f"\n[Sprint 04 Concurrent DHCP Benchmark] {client_count} Clients Leased in Parallel:")
        print(f"  - Leased IP Range: {min(leased_ips)} to {max(leased_ips)}")
        print(f"  - IP Collision Rate: 0.00% (Zero duplicate allocations)")


if __name__ == "__main__":
    unittest.main()
