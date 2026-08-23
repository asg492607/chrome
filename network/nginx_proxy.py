import socket
import threading

try:
    from network.logger import sys_logger
except ImportError:
    try:
        from logger import sys_logger
    except ImportError:
        class DummyLogger:
            def log(self, msg): print(msg)
        sys_logger = DummyLogger()

class NginxProxy:
    def __init__(self, host="127.0.0.1", port=8080):
        self.host = host
        self.port = port
        self.running = False
        self.server_socket = None
        
        # Upstream routes mapping host header to local ports
        self.routes = {
            "asgsearch.local": 8082,
            "myblog.com": 8081,
            "news.com": 8081,
            "localhost": 8081
        }
        
    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_socket.bind((self.host, self.port))
        except Exception as e:
            sys_logger.log(f"[Nginx Error] Failed to bind to {self.host}:{self.port}: {e}")
            return
            
        self.server_socket.listen(10)
        self.running = True
        sys_logger.log(f"[Nginx Proxy] Listening on {self.host}:{self.port}")
        
        thread = threading.Thread(target=self._accept_loop, daemon=True)
        thread.start()

    def stop(self):
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        sys_logger.log("[Nginx Proxy] Stopped")

    def _accept_loop(self):
        while self.running:
            try:
                client_sock, client_addr = self.server_socket.accept()
                # Handle client in a new thread
                thread = threading.Thread(target=self._handle_client, args=(client_sock, client_addr), daemon=True)
                thread.start()
            except OSError:
                break

    def _handle_client(self, client_sock, client_addr):
        try:
            # Read header chunk to identify Host
            request_bytes = client_sock.recv(4096)
            if not request_bytes:
                client_sock.close()
                return
            
            request_text = request_bytes.decode('utf-8', errors='ignore')
            lines = request_text.split('\r\n')
            
            # Find Host header
            host = None
            for line in lines:
                if line.lower().startswith('host:'):
                    # Host: domain:port -> extract domain
                    parts = line.split(':', 1)
                    if len(parts) > 1:
                        host_val = parts[1].strip()
                        host = host_val.split(':')[0]  # Strip port if present
                    break
            
            if not host:
                # 400 Bad Request
                response = (
                    "HTTP/1.1 400 Bad Request\r\n"
                    "Content-Type: text/html\r\n"
                    "Connection: close\r\n\r\n"
                    "<h1>400 Bad Request</h1><p>Missing Host Header.</p>"
                )
                client_sock.sendall(response.encode('utf-8'))
                client_sock.close()
                return

            sys_logger.log(f"[Nginx Proxy] Routing request for host '{host}'...")
            
            upstream_port = self.routes.get(host)
            if not upstream_port:
                # 502 Bad Gateway
                response = (
                    "HTTP/1.1 502 Bad Gateway\r\n"
                    "Content-Type: text/html\r\n"
                    "Connection: close\r\n\r\n"
                    f"<h1>502 Bad Gateway</h1><p>No upstream configured for '{host}'.</p>"
                )
                client_sock.sendall(response.encode('utf-8'))
                client_sock.close()
                return

            # Forward to upstream
            upstream_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            upstream_sock.connect((self.host, upstream_port))
            
            # Send client's request to upstream
            upstream_sock.sendall(request_bytes)
            
            # Receive response from upstream and send back to client
            # (Loop until EOF)
            while True:
                response_chunk = upstream_sock.recv(4096)
                if not response_chunk:
                    break
                client_sock.sendall(response_chunk)
                
            upstream_sock.close()
            
        except Exception as e:
            sys_logger.log(f"[Nginx Proxy Client Handling Error] {e}")
            try:
                # Send 500 Internal Server Error
                response = (
                    "HTTP/1.1 500 Internal Server Error\r\n"
                    "Content-Type: text/html\r\n"
                    "Connection: close\r\n\r\n"
                    f"<h1>500 Internal Server Error</h1><p>{str(e)}</p>"
                )
                client_sock.sendall(response.encode('utf-8'))
            except:
                pass
        finally:
            client_sock.close()

if __name__ == "__main__":
    proxy = NginxProxy()
    proxy.start()
    
    # Keep main thread alive for testing
    import time
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        proxy.stop()
