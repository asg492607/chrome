import socket
import threading
import json
import time

try:
    from network.logger import sys_logger
except ImportError:
    try:
        from logger import sys_logger
    except ImportError:
        class DummyLogger:
            def log(self, msg): print(msg)
        sys_logger = DummyLogger()

class DHCPServer:
    def __init__(self, host="127.0.0.1", port=6767):
        self.host = host
        self.port = port
        self.running = False
        self.socket = None
        self.ip_pool = [f"192.168.1.{i}" for i in range(100, 200)]
        self.active_leases = {}  # client_id -> leased_ip
        self.dns_ip = "192.168.1.53"
        self.gateway_ip = "192.168.1.1"
        self.subnet_mask = "255.255.255.0"

    def start(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.socket.bind((self.host, self.port))
        except Exception as e:
            sys_logger.log(f"[DHCP Server Error] Failed to bind to {self.host}:{self.port}: {e}")
            return
        
        self.running = True
        sys_logger.log(f"[DHCP Server] Started listening on {self.host}:{self.port}")
        
        thread = threading.Thread(target=self._listen_loop, daemon=True)
        thread.start()

    def stop(self):
        self.running = False
        if self.socket:
            self.socket.close()
        sys_logger.log("[DHCP Server] Stopped")

    def _listen_loop(self):
        while self.running:
            try:
                data, addr = self.socket.recvfrom(2048)
                if not data:
                    continue
                
                message = json.loads(data.decode('utf-8'))
                msg_type = message.get("type")
                client_id = message.get("client_id")
                tx_id = message.get("tx_id")

                sys_logger.log(f"[DHCP Server] Received {msg_type} from {client_id} (TX ID: {tx_id})")

                if msg_type == "DISCOVER":
                    # Offer an IP
                    offered_ip = self.active_leases.get(client_id)
                    if not offered_ip:
                        if self.ip_pool:
                            offered_ip = self.ip_pool[0]
                        else:
                            sys_logger.log("[DHCP Server] Error: IP Pool exhausted!")
                            continue
                    
                    response = {
                        "type": "OFFER",
                        "tx_id": tx_id,
                        "ip": offered_ip,
                        "subnet": self.subnet_mask,
                        "router": self.gateway_ip,
                        "dns": self.dns_ip,
                        "lease_time": 86400
                    }
                    self.socket.sendto(json.dumps(response).encode('utf-8'), addr)
                    sys_logger.log(f"[DHCP Server] Sent OFFER {offered_ip} to {client_id}")

                elif msg_type == "REQUEST":
                    requested_ip = message.get("requested_ip")
                    # Allocate IP
                    if requested_ip in self.ip_pool:
                        self.ip_pool.remove(requested_ip)
                    self.active_leases[client_id] = requested_ip
                    
                    response = {
                        "type": "ACK",
                        "tx_id": tx_id,
                        "ip": requested_ip,
                        "subnet": self.subnet_mask,
                        "router": self.gateway_ip,
                        "dns": self.dns_ip,
                        "lease_time": 86400
                    }
                    self.socket.sendto(json.dumps(response).encode('utf-8'), addr)
                    sys_logger.log(f"[DHCP Server] Sent ACK for {requested_ip} to {client_id}")

            except OSError:
                break
            except Exception as e:
                sys_logger.log(f"[DHCP Server Loop Error] {e}")


def run_dhcp_client(server_host="127.0.0.1", server_port=6767, client_id="AsgBrowser-Client"):
    """
    Performs the DHCP DORA process and returns lease details.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2.0)
    tx_id = int(time.time() * 1000) & 0xFFFF
    
    try:
        # 1. Send DISCOVER
        discover_msg = {
            "type": "DISCOVER",
            "client_id": client_id,
            "tx_id": tx_id
        }
        print(f"[DHCP Client] Sending DISCOVER (TX: {tx_id})")
        sock.sendto(json.dumps(discover_msg).encode('utf-8'), (server_host, server_port))

        # 2. Receive OFFER
        data, addr = sock.recvfrom(2048)
        offer = json.loads(data.decode('utf-8'))
        if offer.get("type") != "OFFER" or offer.get("tx_id") != tx_id:
            raise Exception("Invalid DHCP OFFER received")
        
        offered_ip = offer.get("ip")
        print(f"[DHCP Client] Received OFFER: {offered_ip}")

        # 3. Send REQUEST
        request_msg = {
            "type": "REQUEST",
            "client_id": client_id,
            "tx_id": tx_id,
            "requested_ip": offered_ip
        }
        print(f"[DHCP Client] Sending REQUEST for {offered_ip}")
        sock.sendto(json.dumps(request_msg).encode('utf-8'), (server_host, server_port))

        # 4. Receive ACK
        data, addr = sock.recvfrom(2048)
        ack = json.loads(data.decode('utf-8'))
        if ack.get("type") != "ACK" or ack.get("tx_id") != tx_id:
            raise Exception("Invalid DHCP ACK received")
        
        print(f"[DHCP Client] Received ACK. Configuration leased successfully!")
        return {
            "ip": ack.get("ip"),
            "subnet": ack.get("subnet"),
            "router": ack.get("router"),
            "dns": ack.get("dns"),
            "lease_time": ack.get("lease_time")
        }

    except socket.timeout:
        print("[DHCP Client] Error: DHCP server timed out!")
        return None
    except Exception as e:
        print(f"[DHCP Client Error] {e}")
        return None
    finally:
        sock.close()

if __name__ == "__main__":
    # Test DHCP cycle locally
    server = DHCPServer()
    server.start()
    time.sleep(0.5)
    
    config = run_dhcp_client()
    print("Leased configuration:", config)
    
    server.stop()
