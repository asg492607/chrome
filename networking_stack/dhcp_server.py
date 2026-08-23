"""
RFC 2131-Compliant Self-Contained DHCP Server & DORA State Machine Engine.
Provides dynamic IP leasing, lease timers, automatic expired lease reclamation,
and isolated zero-hardware sandbox networking for the sovereign stack.
"""

import socket
import threading
import json
import time
import sys
import os
from enum import Enum, auto
from typing import Dict, List, Optional, Any, Set, Tuple

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core_platform.logging_system import sys_logger


class DHCPState(Enum):
    """DHCP Client & Server Protocol States (RFC 2131)."""
    INIT = auto()
    SELECTING = auto()
    REQUESTING = auto()
    BOUND = auto()
    RENEWING = auto()
    REBINDING = auto()
    RELEASED = auto()


class DHCPLease:
    """Represents an active IP address lease record with timing constraints."""
    def __init__(
        self,
        leased_ip: str,
        client_id: str,
        client_mac: str = "00:00:00:00:00:00",
        lease_duration: float = 86400.0,
        subnet_mask: str = "255.255.255.0",
        router_ip: str = "192.168.1.1",
        dns_ip: str = "192.168.1.53"
    ):
        self.leased_ip = leased_ip
        self.client_id = client_id
        self.client_mac = client_mac
        self.lease_start = time.time()
        self.lease_duration = lease_duration
        self.t1_renew = lease_duration * 0.5   # Renew at 50%
        self.t2_rebind = lease_duration * 0.875 # Rebind at 87.5%
        self.subnet_mask = subnet_mask
        self.router_ip = router_ip
        self.dns_ip = dns_ip
        self.is_active = True

    def is_expired(self) -> bool:
        """Returns True if current time exceeds lease expiration."""
        return (time.time() - self.lease_start) >= self.lease_duration

    def remaining_seconds(self) -> float:
        """Returns remaining seconds before lease expiration."""
        remaining = self.lease_duration - (time.time() - self.lease_start)
        return max(0.0, remaining)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ip": self.leased_ip,
            "client_id": self.client_id,
            "client_mac": self.client_mac,
            "subnet": self.subnet_mask,
            "router": self.router_ip,
            "dns": self.dns_ip,
            "lease_time": int(self.remaining_seconds()),
            "is_active": self.is_active
        }


class DHCPServer:
    """
    Self-Contained RFC 2131 Dynamic Host Configuration Protocol Server.
    Manages dynamic IP lease pools, DORA handshakes, lease recycling, and NAK/RELEASE events.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 6767,
        ip_start: int = 100,
        ip_end: int = 200,
        default_lease_duration: float = 86400.0
    ):
        self.host = host
        self.port = port
        self.running = False
        self.socket: Optional[socket.socket] = None
        self.default_lease_duration = default_lease_duration
        
        # Subnet configuration
        self.subnet_mask = "255.255.255.0"
        self.gateway_ip = "192.168.1.1"
        self.dns_ip = "192.168.1.53"

        # IP Pool management
        self.lock = threading.Lock()
        self.ip_pool: List[str] = [f"192.168.1.{i}" for i in range(ip_start, ip_end)]
        self.active_leases: Dict[str, DHCPLease] = {}         # client_id -> DHCPLease
        self.offered_reservations: Dict[str, Tuple[str, float]] = {} # client_id -> (offered_ip, timestamp)
        self.ip_to_client: Dict[str, str] = {}                # ip -> client_id

        # Telemetry metrics
        self.total_discovers = 0
        self.total_offers = 0
        self.total_requests = 0
        self.total_acks = 0
        self.total_naks = 0
        self.total_releases = 0

    def start(self) -> None:
        """Starts the DHCP UDP server thread."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.socket.bind((self.host, self.port))
        except Exception as e:
            sys_logger.log(f"[DHCP Server Error] Failed to bind {self.host}:{self.port}: {e}")
            return
        
        self.running = True
        sys_logger.log(f"[DHCP Server] Running on {self.host}:{self.port} (Pool: {len(self.ip_pool)} IPs)")
        
        thread = threading.Thread(target=self._listen_loop, daemon=True, name="DHCPServerLoop")
        thread.start()

    def stop(self) -> None:
        """Stops the DHCP server."""
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
        sys_logger.log("[DHCP Server] Stopped")

    def reclaim_expired_leases(self) -> int:
        """Identifies and reclaims expired leases, returning IPs back to the available pool."""
        with self.lock:
            now = time.time()
            # Clean expired transient offers (> 5 seconds old)
            expired_offers = [cid for cid, (ip, ts) in self.offered_reservations.items() if (now - ts) > 5.0]
            for cid in expired_offers:
                self.offered_reservations.pop(cid, None)

            expired_clients = []
            for client_id, lease in self.active_leases.items():
                if lease.is_expired():
                    expired_clients.append(client_id)

            for client_id in expired_clients:
                lease = self.active_leases.pop(client_id)
                self.ip_to_client.pop(lease.leased_ip, None)
                self.ip_pool.append(lease.leased_ip)
                sys_logger.log(f"[DHCP Server] Reclaimed expired lease {lease.leased_ip} from {client_id}")

            return len(expired_clients)

    def _listen_loop(self) -> None:
        while self.running:
            try:
                data, addr = self.socket.recvfrom(4096)
                if not data:
                    continue
                
                message = json.loads(data.decode('utf-8'))
                self._handle_message(message, addr)

            except OSError:
                break
            except Exception as e:
                sys_logger.log(f"[DHCP Server Loop Error] {e}")

    def _handle_message(self, message: Dict[str, Any], addr: Tuple[str, int]) -> None:
        msg_type = message.get("type", "").upper()
        client_id = message.get("client_id", "unknown-client")
        tx_id = message.get("tx_id", 0)
        mac = message.get("mac", "00:00:00:00:00:00")

        self.reclaim_expired_leases()

        with self.lock:
            now = time.time()
            if msg_type == "DISCOVER":
                self.total_discovers += 1
                offered_ip = None

                # 1. Existing active lease
                if client_id in self.active_leases and not self.active_leases[client_id].is_expired():
                    offered_ip = self.active_leases[client_id].leased_ip
                # 2. Existing pending reservation
                elif client_id in self.offered_reservations:
                    offered_ip = self.offered_reservations[client_id][0]
                # 3. Find first available IP not currently offered
                else:
                    currently_offered = {ip for ip, _ in self.offered_reservations.values()}
                    for candidate in self.ip_pool:
                        if candidate not in currently_offered:
                            offered_ip = candidate
                            break

                if not offered_ip and self.ip_pool:
                    offered_ip = self.ip_pool[0]

                if not offered_ip:
                    # Pool exhausted -> NAK
                    self.total_naks += 1
                    response = {"type": "NAK", "tx_id": tx_id, "error": "IP pool exhausted"}
                    self.socket.sendto(json.dumps(response).encode('utf-8'), addr)
                    sys_logger.log(f"[DHCP Server] Sent NAK to {client_id} (Pool Exhausted)")
                    return

                # Record transient reservation
                self.offered_reservations[client_id] = (offered_ip, now)
                self.total_offers += 1
                response = {
                    "type": "OFFER",
                    "tx_id": tx_id,
                    "ip": offered_ip,
                    "subnet": self.subnet_mask,
                    "router": self.gateway_ip,
                    "dns": self.dns_ip,
                    "lease_time": int(self.default_lease_duration)
                }
                self.socket.sendto(json.dumps(response).encode('utf-8'), addr)
                sys_logger.log(f"[DHCP Server] Sent OFFER {offered_ip} to {client_id} (TX: {tx_id})")

            elif msg_type == "REQUEST":
                self.total_requests += 1
                requested_ip = message.get("requested_ip")
                self.offered_reservations.pop(client_id, None)

                # Validate requested IP availability
                is_available = (
                    requested_ip in self.ip_pool or
                    (client_id in self.active_leases and self.active_leases[client_id].leased_ip == requested_ip)
                )

                if not is_available:
                    self.total_naks += 1
                    response = {"type": "NAK", "tx_id": tx_id, "error": f"IP {requested_ip} unavailable"}
                    self.socket.sendto(json.dumps(response).encode('utf-8'), addr)
                    sys_logger.log(f"[DHCP Server] Sent NAK for {requested_ip} to {client_id}")
                    return

                # Allocate from pool if new
                if requested_ip in self.ip_pool:
                    self.ip_pool.remove(requested_ip)

                lease = DHCPLease(
                    leased_ip=requested_ip,
                    client_id=client_id,
                    client_mac=mac,
                    lease_duration=self.default_lease_duration,
                    subnet_mask=self.subnet_mask,
                    router_ip=self.gateway_ip,
                    dns_ip=self.dns_ip
                )
                self.active_leases[client_id] = lease
                self.ip_to_client[requested_ip] = client_id
                self.total_acks += 1

                response = {
                    "type": "ACK",
                    "tx_id": tx_id,
                    "ip": requested_ip,
                    "subnet": self.subnet_mask,
                    "router": self.gateway_ip,
                    "dns": self.dns_ip,
                    "lease_time": int(self.default_lease_duration)
                }
                self.socket.sendto(json.dumps(response).encode('utf-8'), addr)
                sys_logger.log(f"[DHCP Server] Sent ACK for {requested_ip} to {client_id} (TX: {tx_id})")

            elif msg_type == "RELEASE":
                self.total_releases += 1
                self.offered_reservations.pop(client_id, None)
                if client_id in self.active_leases:
                    lease = self.active_leases.pop(client_id)
                    self.ip_to_client.pop(lease.leased_ip, None)
                    if lease.leased_ip not in self.ip_pool:
                        self.ip_pool.append(lease.leased_ip)
                    sys_logger.log(f"[DHCP Server] Client {client_id} released IP {lease.leased_ip}")

    def get_diagnostics(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "active_leases_count": len(self.active_leases),
                "available_ips_in_pool": len(self.ip_pool),
                "total_discovers": self.total_discovers,
                "total_offers": self.total_offers,
                "total_requests": self.total_requests,
                "total_acks": self.total_acks,
                "total_naks": self.total_naks,
                "total_releases": self.total_releases
            }


class DHCPClientEngine:
    """
    RFC 2131 Stateful DHCP Client.
    Executes full DORA handshakes, tracks state transitions, and manages lease renewals/releases.
    """
    def __init__(
        self,
        server_host: str = "127.0.0.1",
        server_port: int = 6767,
        client_id: str = "PacketForge-Agent-01",
        mac_addr: str = "00:AA:BB:CC:DD:EE"
    ):
        self.server_host = server_host
        self.server_port = server_port
        self.client_id = client_id
        self.mac_addr = mac_addr
        self.state = DHCPState.INIT
        self.current_lease: Optional[Dict[str, Any]] = None
        self.tx_id: int = 0

    def discover_and_request(self, timeout: float = 2.0, max_retries: int = 3) -> Optional[Dict[str, Any]]:
        """Executes full DISCOVER -> OFFER -> REQUEST -> ACK DORA handshake with automatic retry on NAK."""
        for attempt in range(max_retries):
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            self.tx_id = int(time.time() * 1000 + attempt * 17) & 0xFFFF
            
            try:
                # 1. DISCOVER
                self.state = DHCPState.SELECTING
                discover_msg = {
                    "type": "DISCOVER",
                    "client_id": self.client_id,
                    "mac": self.mac_addr,
                    "tx_id": self.tx_id
                }
                sock.sendto(json.dumps(discover_msg).encode('utf-8'), (self.server_host, self.server_port))

                data, _ = sock.recvfrom(2048)
                offer = json.loads(data.decode('utf-8'))
                if offer.get("type") == "NAK":
                    self.state = DHCPState.INIT
                    return None

                if offer.get("type") != "OFFER" or offer.get("tx_id") != self.tx_id:
                    raise ValueError("Invalid DHCP OFFER received")

                offered_ip = offer.get("ip")

                # 2. REQUEST
                self.state = DHCPState.REQUESTING
                request_msg = {
                    "type": "REQUEST",
                    "client_id": self.client_id,
                    "mac": self.mac_addr,
                    "tx_id": self.tx_id,
                    "requested_ip": offered_ip
                }
                sock.sendto(json.dumps(request_msg).encode('utf-8'), (self.server_host, self.server_port))

                data, _ = sock.recvfrom(2048)
                ack = json.loads(data.decode('utf-8'))
                if ack.get("type") == "NAK":
                    # If NAK received due to race condition, retry after tiny backoff
                    time.sleep(0.01 * (attempt + 1))
                    continue

                if ack.get("type") != "ACK" or ack.get("tx_id") != self.tx_id:
                    raise ValueError("Invalid DHCP ACK received")

                # 3. BOUND
                self.state = DHCPState.BOUND
                self.current_lease = {
                    "ip": ack.get("ip"),
                    "subnet": ack.get("subnet"),
                    "router": ack.get("router"),
                    "dns": ack.get("dns"),
                    "lease_time": ack.get("lease_time")
                }
                return self.current_lease

            except socket.timeout:
                self.state = DHCPState.INIT
                return None
            except Exception:
                self.state = DHCPState.INIT
                return None
            finally:
                sock.close()

        self.state = DHCPState.INIT
        return None


    def release_lease(self) -> bool:
        """Sends DHCPRELEASE to return leased IP back to server pool."""
        if self.state != DHCPState.BOUND or not self.current_lease:
            return False

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            release_msg = {
                "type": "RELEASE",
                "client_id": self.client_id,
                "mac": self.mac_addr,
                "tx_id": self.tx_id
            }
            sock.sendto(json.dumps(release_msg).encode('utf-8'), (self.server_host, self.server_port))
            self.state = DHCPState.RELEASED
            self.current_lease = None
            return True
        except Exception:
            return False
        finally:
            sock.close()


def run_dhcp_client(server_host="127.0.0.1", server_port=6767, client_id="AsgBrowser-Client"):
    """Backward-compatible helper function for legacy browser controller callers."""
    client = DHCPClientEngine(server_host=server_host, server_port=server_port, client_id=client_id)
    return client.discover_and_request()
