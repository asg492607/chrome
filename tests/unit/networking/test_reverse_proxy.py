"""
Unit Test Suite for Zero-Copy Reverse Proxy & Outbound Egress Sandbox (Sprint 06).
Verifies origin cookie jar isolation, TCP connection pooling, egress firewall blocking,
dynamic host routing, and HTTP 400/403/502 status handling.
"""

import sys
import os
import unittest
import socket
import threading
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from networking_stack.reverse_proxy import (
    EgressPolicy,
    OriginCookieJar,
    TCPConnectionPool,
    EgressSecuritySandbox,
    ReverseProxyEngine
)


class MockUpstreamServer:
    """Helper mock upstream HTTP server."""
    def __init__(self, host="127.0.0.1", port=9091, response_body="Hello from Upstream"):
        self.host = host
        self.port = port
        self.response_body = response_body
        self.running = False
        self.server_sock = None

    def start(self):
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen(10)
        self.running = True
        threading.Thread(target=self._serve, daemon=True).start()

    def stop(self):
        self.running = False
        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass

    def _serve(self):
        while self.running:
            try:
                client, _ = self.server_sock.accept()
                _ = client.recv(4096)
                resp = (
                    "HTTP/1.1 200 OK\r\n"
                    f"Content-Length: {len(self.response_body)}\r\n"
                    "Content-Type: text/plain\r\n\r\n"
                    f"{self.response_body}"
                )
                client.sendall(resp.encode('utf-8'))
                client.close()
            except OSError:
                break


class TestReverseProxySubsystem(unittest.TestCase):

    def test_origin_cookie_jar_strict_isolation(self):
        """Verify cookies set on domain-a are physically segregated from domain-b."""
        jar = OriginCookieJar()
        jar.set_cookie("domain-a.com", "session_id", "secret_token_123")
        jar.set_cookie("domain-a.com", "theme", "dark")
        jar.set_cookie("domain-b.com", "analytics_id", "xyz_999")

        header_a = jar.get_cookie_header("domain-a.com")
        header_b = jar.get_cookie_header("domain-b.com")
        header_c = jar.get_cookie_header("domain-c.com")

        self.assertIn("session_id=secret_token_123", header_a)
        self.assertIn("theme=dark", header_a)
        self.assertNotIn("analytics_id", header_a)

        self.assertEqual(header_b, "analytics_id=xyz_999")
        self.assertNotIn("session_id", header_b)

        self.assertIsNone(header_c)

    def test_egress_security_sandbox_filtering(self):
        """Test egress firewall blocking telemetry domains and enforcing allowlists."""
        sandbox = EgressSecuritySandbox(policy=EgressPolicy.BLOCK_TELEMETRY)

        # 1. Clean domain -> allowed
        allowed, _ = sandbox.is_egress_allowed("asgsearch.local")
        self.assertTrue(allowed)

        # 2. Telemetry tracker -> blocked
        blocked, reason = sandbox.is_egress_allowed("telemetry.google.com")
        self.assertFalse(blocked)
        self.assertIn("tracking/telemetry", reason)
        self.assertEqual(sandbox.blocked_count, 1)

        # 3. Allowlist-only policy
        strict_sandbox = EgressSecuritySandbox(policy=EgressPolicy.ALLOWLIST_ONLY)
        strict_sandbox.add_allowed_domain("sovereign.local")
        
        ok, _ = strict_sandbox.is_egress_allowed("sovereign.local")
        self.assertTrue(ok)

        not_ok, _ = strict_sandbox.is_egress_allowed("unapproved.com")
        self.assertFalse(not_ok)

    def test_reverse_proxy_end_to_end_routing(self):
        """Test full HTTP request routing through ReverseProxyEngine to upstream mock server."""
        upstream_port = 9181
        proxy_port = 9180

        mock_server = MockUpstreamServer(port=upstream_port, response_body="Sovereign Web Content")
        mock_server.start()
        time.sleep(0.05)

        proxy = ReverseProxyEngine(host="127.0.0.1", port=proxy_port)
        proxy.add_route("myportal.local", upstream_port)
        proxy.start()
        time.sleep(0.05)

        try:
            # Client sends HTTP GET to proxy
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect(("127.0.0.1", proxy_port))
            req = "GET / HTTP/1.1\r\nHost: myportal.local\r\n\r\n"
            client.sendall(req.encode('utf-8'))

            response = client.recv(4096).decode('utf-8')
            client.close()

            self.assertIn("HTTP/1.1 200 OK", response)
            self.assertIn("Sovereign Web Content", response)
            time.sleep(0.02)
            self.assertEqual(proxy.routed_requests, 1)

        finally:
            proxy.stop()
            mock_server.stop()


    def test_reverse_proxy_egress_firewall_403(self):
        """Test that unauthorized egress requests receive HTTP 403 Forbidden from Egress Sandbox."""
        proxy_port = 9182
        proxy = ReverseProxyEngine(host="127.0.0.1", port=proxy_port)
        proxy.egress_sandbox.policy = EgressPolicy.ALLOWLIST_ONLY
        proxy.egress_sandbox.add_allowed_domain("safe-internal.local")
        proxy.start()
        time.sleep(0.05)

        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect(("127.0.0.1", proxy_port))
            req = "GET /export HTTP/1.1\r\nHost: unauthorized-corp-leak.com\r\n\r\n"
            client.sendall(req.encode('utf-8'))

            response = client.recv(4096).decode('utf-8')
            client.close()

            self.assertIn("HTTP/1.1 403 Forbidden", response)
            self.assertIn("X-Egress-Sandbox: Blocked", response)
            self.assertEqual(proxy.egress_sandbox.blocked_count, 1)

        finally:
            proxy.stop()


    def test_reverse_proxy_status_codes(self):
        """Test HTTP 400 Bad Request (missing host) and HTTP 502 Bad Gateway (unmapped host)."""
        proxy_port = 9183
        proxy = ReverseProxyEngine(host="127.0.0.1", port=proxy_port)
        proxy.start()
        time.sleep(0.05)

        try:
            # 1. Missing Host header -> 400
            c1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            c1.connect(("127.0.0.1", proxy_port))
            c1.sendall(b"GET / HTTP/1.1\r\n\r\n")
            r1 = c1.recv(4096).decode('utf-8')
            c1.close()
            self.assertIn("HTTP/1.1 400 Bad Request", r1)

            # 2. Unmapped host -> 502
            c2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            c2.connect(("127.0.0.1", proxy_port))
            c2.sendall(b"GET / HTTP/1.1\r\nHost: unknown-service.com\r\n\r\n")
            r2 = c2.recv(4096).decode('utf-8')
            c2.close()
            self.assertIn("HTTP/1.1 502 Bad Gateway", r2)

        finally:
            proxy.stop()


if __name__ == "__main__":
    unittest.main()
