import socket
import threading
import json

try:
    from network.logger import sys_logger
except ImportError:
    try:
        from logger import sys_logger
    except ImportError:
        class DummyLogger:
            def log(self, msg): print(msg)
        sys_logger = DummyLogger()

class DNSServer:
    def __init__(self, host="127.0.0.1", port=5353):
        self.host = host
        self.port = port
        self.running = False
        self.socket = None
        self.records = {
            "asgsearch.local": "127.0.0.1",
            "myblog.com": "127.0.0.1",
            "news.com": "127.0.0.1",
            "localhost": "127.0.0.1"
        }

    def start(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.socket.bind((self.host, self.port))
        except Exception as e:
            sys_logger.log(f"[DNS Server Error] Failed to bind to {self.host}:{self.port}: {e}")
            return
        
        self.running = True
        sys_logger.log(f"[DNS Server] Started listening on {self.host}:{self.port}")
        
        thread = threading.Thread(target=self._listen_loop, daemon=True)
        thread.start()

    def stop(self):
        self.running = False
        if self.socket:
            self.socket.close()
        sys_logger.log("[DNS Server] Stopped")

    def _listen_loop(self):
        while self.running:
            try:
                data, addr = self.socket.recvfrom(2048)
                if not data:
                    continue
                
                message = json.loads(data.decode('utf-8'))
                msg_type = message.get("type")
                domain = message.get("domain")

                sys_logger.log(f"[DNS Server] Query received for '{domain}' from {addr}")

                if msg_type == "QUERY" and domain in self.records:
                    response = {
                        "type": "RESPONSE",
                        "domain": domain,
                        "ip": self.records[domain],
                        "status": "SUCCESS"
                    }
                else:
                    response = {
                        "type": "RESPONSE",
                        "domain": domain,
                        "ip": None,
                        "status": "NXDOMAIN"
                    }
                
                self.socket.sendto(json.dumps(response).encode('utf-8'), addr)
                sys_logger.log(f"[DNS Server] Resolved '{domain}' -> {response.get('ip')} ({response.get('status')})")

            except OSError:
                break
            except Exception as e:
                sys_logger.log(f"[DNS Server Loop Error] {e}")


def resolve_dns(domain, dns_server_host="127.0.0.1", dns_server_port=5353):
    """
    Simulates a DNS resolver query over UDP.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2.0)
    
    query = {
        "type": "QUERY",
        "domain": domain
    }
    
    try:
        print(f"[DNS Client] Querying DNS server for domain '{domain}'...")
        sock.sendto(json.dumps(query).encode('utf-8'), (dns_server_host, dns_server_port))
        
        data, addr = sock.recvfrom(2048)
        response = json.loads(data.decode('utf-8'))
        
        if response.get("status") == "SUCCESS":
            print(f"[DNS Client] Resolved '{domain}' -> {response.get('ip')}")
            return response.get("ip")
        else:
            print(f"[DNS Client] DNS Resolution failed (status: {response.get('status')})")
            return None
            
    except socket.timeout:
        print(f"[DNS Client] Timeout querying DNS for '{domain}'")
        return None
    except Exception as e:
        print(f"[DNS Client Error] {e}")
        return None
    finally:
        sock.close()

if __name__ == "__main__":
    server = DNSServer()
    server.start()
    
    import time
    time.sleep(0.5)
    
    ip = resolve_dns("asgsearch.local")
    print(f"Resolved IP: {ip}")
    
    ip2 = resolve_dns("unknown.com")
    print(f"Resolved IP: {ip2}")
    
    server.stop()
