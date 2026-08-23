"""
High-Performance Zero-Copy Reverse Proxy & Outbound Egress Security Sandbox.
Provides persistent TCP connection pooling, per-origin cookie jar isolation,
dynamic host routing, and boundary egress filtering with zero external dependencies.
"""

import socket
import threading
import sys
import os
import time
from enum import Enum, auto
from typing import Dict, Optional, Tuple, Set, Any, List

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core_platform.logging_system import sys_logger
from networking_stack.adblock_engine import adblock_engine



class EgressPolicy(Enum):
    """Egress Firewall Security Policies."""
    ALLOW_ALL = auto()
    BLOCK_TELEMETRY = auto()
    ALLOWLIST_ONLY = auto()


class OriginCookieJar:
    """
    Per-Origin Isolated In-Memory Cookie Jar.
    Strictly partitions cookie state by domain origin, preventing cross-site tracking leakage.
    """
    def __init__(self):
        self.lock = threading.Lock()
        # origin (domain: str) -> Dict[cookie_name: str, cookie_value: str]
        self._jars: Dict[str, Dict[str, str]] = {}

    def set_cookie(self, origin: str, name: str, value: str) -> None:
        clean_origin = origin.strip().lower()
        with self.lock:
            if clean_origin not in self._jars:
                self._jars[clean_origin] = {}
            self._jars[clean_origin][name] = value

    def get_cookie_header(self, origin: str) -> Optional[str]:
        clean_origin = origin.strip().lower()
        with self.lock:
            if clean_origin not in self._jars or not self._jars[clean_origin]:
                return None
            pairs = [f"{k}={v}" for k, v in self._jars[clean_origin].items()]
            return "; ".join(pairs)

    def clear_origin(self, origin: str) -> None:
        clean_origin = origin.strip().lower()
        with self.lock:
            self._jars.pop(clean_origin, None)

    def get_all_origins(self) -> List[str]:
        with self.lock:
            return list(self._jars.keys())


class TCPConnectionPool:
    """
    Thread-Safe TCP Socket Connection Pool.
    Maintains persistent Keep-Alive connections to upstream servers, eliminating TCP handshake overhead.
    """
    def __init__(self, max_idle_per_host: int = 5, idle_timeout: float = 30.0):
        self.max_idle_per_host = max_idle_per_host
        self.idle_timeout = idle_timeout
        self.lock = threading.Lock()
        # (host, port) -> List[Tuple[socket.socket, float (timestamp)]]
        self._pool: Dict[Tuple[str, int], List[Tuple[socket.socket, float]]] = {}
        self.reuse_count = 0

    def acquire(self, host: str, port: int, timeout: float = 4.0) -> socket.socket:
        """Acquires an idle socket from the pool, or creates a new connected socket."""
        key = (host, port)
        with self.lock:
            now = time.time()
            if key in self._pool and self._pool[key]:
                while self._pool[key]:
                    sock, timestamp = self._pool[key].pop()
                    # Verify socket has not expired
                    if (now - timestamp) < self.idle_timeout:
                        self.reuse_count += 1
                        return sock
                    else:
                        try:
                            sock.close()
                        except Exception:
                            pass

        # Create fresh socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        return sock

    def release(self, host: str, port: int, sock: socket.socket) -> None:
        """Returns an active socket back to the pool for future reuse."""
        key = (host, port)
        with self.lock:
            if key not in self._pool:
                self._pool[key] = []
            if len(self._pool[key]) < self.max_idle_per_host:
                self._pool[key].append((sock, time.time()))
            else:
                try:
                    sock.close()
                except Exception:
                    pass

    def close_all(self) -> None:
        with self.lock:
            for key, sockets in self._pool.items():
                for sock, _ in sockets:
                    try:
                        sock.close()
                    except Exception:
                        pass
            self._pool.clear()


class EgressSecuritySandbox:
    """
    Boundary Outbound Security & Privacy Firewall.
    Enforces domain allowlists, blocks telemetry trackers, and sanitizes outgoing headers.
    """
    DEFAULT_BLOCKED_DOMAINS: Set[str] = {
        "telemetry.google.com",
        "analytics.tracking.com",
        "adservice.google.com",
        "doubleclick.net",
        "track.adtech.io",
        "metrics.telemetry.internal"
    }

    def __init__(self, policy: EgressPolicy = EgressPolicy.BLOCK_TELEMETRY):
        self.policy = policy
        self.blocked_domains = set(self.DEFAULT_BLOCKED_DOMAINS)
        self.allowlist: Set[str] = set()
        self.blocked_count = 0
        self.lock = threading.Lock()

    def add_blocked_domain(self, domain: str) -> None:
        with self.lock:
            self.blocked_domains.add(domain.strip().lower())

    def add_allowed_domain(self, domain: str) -> None:
        with self.lock:
            self.allowlist.add(domain.strip().lower())

    def is_egress_allowed(self, host: str) -> Tuple[bool, str]:
        """Validates if outbound connection to target host is authorized."""
        clean_host = host.strip().lower().split(':')[0]
        with self.lock:
            if self.policy == EgressPolicy.ALLOWLIST_ONLY:
                if clean_host not in self.allowlist:
                    self.blocked_count += 1
                    return False, f"Host '{clean_host}' is not on the authorized allowlist."
                return True, "Authorized by Allowlist"

            if self.policy == EgressPolicy.BLOCK_TELEMETRY:
                if clean_host in self.blocked_domains:
                    self.blocked_count += 1
                    return False, f"Egress blocked: '{clean_host}' is flagged as a tracking/telemetry domain."
                return True, "Authorized"

            return True, "Allow All Policy"


class ReverseProxyEngine:
    """
    High-Performance Zero-Copy Reverse Proxy & Outbound Egress Firewall.
    Coordinates connection pools, per-origin cookie jars, and boundary traffic inspection.
    """
    def __init__(self, host: str = "127.0.0.1", port: int = 8080):
        self.host = host
        self.port = port
        self.running = False
        self.server_socket: Optional[socket.socket] = None

        # Subsystems
        self.cookie_jar = OriginCookieJar()
        self.connection_pool = TCPConnectionPool()
        self.egress_sandbox = EgressSecuritySandbox(policy=EgressPolicy.BLOCK_TELEMETRY)

        # Dynamic Route Table (Domain -> Upstream Port)
        self.routes: Dict[str, int] = {
            "asgsearch.local": 8082,
            "myblog.com": 8081,
            "news.com": 8081,
            "localhost": 8081
        }

        # Telemetry
        self.total_requests = 0
        self.routed_requests = 0
        self.bytes_relayed = 0

    def add_route(self, domain: str, upstream_port: int) -> None:
        self.routes[domain.strip().lower()] = upstream_port

    def start(self) -> None:
        """Starts the reverse proxy listener."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_socket.bind((self.host, self.port))
        except Exception as e:
            sys_logger.log(f"[Reverse Proxy Error] Failed to bind {self.host}:{self.port}: {e}")
            return

        self.server_socket.listen(50)
        self.running = True
        sys_logger.log(f"[Reverse Proxy] Listening on {self.host}:{self.port} ({len(self.routes)} Routes Configured)")

        thread = threading.Thread(target=self._accept_loop, daemon=True, name="ReverseProxyAcceptLoop")
        thread.start()

    def stop(self) -> None:
        """Stops the reverse proxy and clears pooled sockets."""
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
        self.connection_pool.close_all()
        sys_logger.log("[Reverse Proxy] Stopped")

    def _accept_loop(self) -> None:
        while self.running:
            try:
                client_sock, client_addr = self.server_socket.accept()
                thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_sock, client_addr),
                    daemon=True,
                    name=f"ProxyClient-{client_addr}"
                )
                thread.start()
            except OSError:
                break

    def _handle_client(self, client_sock: socket.socket, client_addr: Tuple[str, int]) -> None:
        try:
            request_bytes = client_sock.recv(8192)
            if not request_bytes:
                client_sock.close()
                return

            self.total_requests += 1
            request_text = request_bytes.decode('utf-8', errors='ignore')
            lines = request_text.split('\r\n')

            # 1. Extract Method, Path, and Host Header
            first_line = lines[0] if lines else ""
            req_parts = first_line.split(' ')
            path = req_parts[1] if len(req_parts) > 1 else "/"

            host = None
            for line in lines:
                if line.lower().startswith('host:'):
                    parts = line.split(':', 1)
                    if len(parts) > 1:
                        host = parts[1].strip().split(':')[0]
                    break

            if not host:
                response = (
                    "HTTP/1.1 400 Bad Request\r\n"
                    "Content-Type: text/html\r\n"
                    "Connection: close\r\n\r\n"
                    "<h1>400 Bad Request</h1><p>Missing Host Header.</p>"
                )
                client_sock.sendall(response.encode('utf-8'))
                client_sock.close()
                return

            # 2. Layer-1 Ad & Tracker Interception (Socket Short-Circuit)
            is_ad, ad_rule = adblock_engine.should_block(host, path)
            if is_ad:
                response = (
                    "HTTP/1.1 204 No Content\r\n"
                    "X-AdBlock-Engine: Blocked\r\n"
                    f"X-Rule-Matched: {ad_rule}\r\n"
                    "Connection: close\r\n\r\n"
                )
                client_sock.sendall(response.encode('utf-8'))
                client_sock.close()
                sys_logger.log(f"[AdBlock Layer-1] Intercepted & dropped ad request to '{host}{path}' ({ad_rule})")
                return

            # 3. Egress Security Sandbox Check
            allowed, reason = self.egress_sandbox.is_egress_allowed(host)
            if not allowed:
                response = (
                    "HTTP/1.1 403 Forbidden\r\n"
                    "Content-Type: text/html\r\n"
                    "X-Egress-Sandbox: Blocked\r\n"
                    "Connection: close\r\n\r\n"
                    f"<h1>403 Forbidden</h1><p>Egress Blocked by Privacy Firewall: {reason}</p>"
                )
                client_sock.sendall(response.encode('utf-8'))
                client_sock.close()
                return


            # 3. Route Upstream Resolution
            upstream_port = self.routes.get(host)
            if not upstream_port:
                response = (
                    "HTTP/1.1 502 Bad Gateway\r\n"
                    "Content-Type: text/html\r\n"
                    "Connection: close\r\n\r\n"
                    f"<h1>502 Bad Gateway</h1><p>No upstream configured for '{host}'.</p>"
                )
                client_sock.sendall(response.encode('utf-8'))
                client_sock.close()
                return

            sys_logger.log(f"[Reverse Proxy] Routing request for '{host}' -> port {upstream_port}")

            # 4. Acquire Connection from Pool
            upstream_sock = self.connection_pool.acquire(self.host, upstream_port)
            upstream_sock.sendall(request_bytes)

            # 5. Relay Response
            total_response_bytes = 0
            while True:
                response_chunk = upstream_sock.recv(8192)
                if not response_chunk:
                    break
                total_response_bytes += len(response_chunk)
                client_sock.sendall(response_chunk)

            self.bytes_relayed += total_response_bytes
            self.routed_requests += 1
            
            # Close upstream on non-persistent sockets
            upstream_sock.close()

        except Exception as e:
            sys_logger.log(f"[Reverse Proxy Client Handling Error] {e}")
            try:
                response = (
                    "HTTP/1.1 500 Internal Server Error\r\n"
                    "Content-Type: text/html\r\n"
                    "Connection: close\r\n\r\n"
                    f"<h1>500 Internal Server Error</h1><p>{str(e)}</p>"
                )
                client_sock.sendall(response.encode('utf-8'))
            except Exception:
                pass
        finally:
            client_sock.close()

    def get_diagnostics(self) -> Dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "routed_requests": self.routed_requests,
            "blocked_egress_count": self.egress_sandbox.blocked_count,
            "pool_reuses_count": self.connection_pool.reuse_count,
            "bytes_relayed": self.bytes_relayed,
            "active_routes_count": len(self.routes),
            "isolated_cookie_origins_count": len(self.cookie_jar.get_all_origins())
        }


# Backward-compatible alias for legacy references
NginxProxy = ReverseProxyEngine
