import socket
import threading
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core_platform.logging_system import sys_logger

class MockWebServer:
    def __init__(self, host="127.0.0.1", port=8081, web_root="mock_web"):
        self.host = host
        self.port = port
        self.web_root = web_root
        self.running = False
        self.server_socket = None

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_socket.bind((self.host, self.port))
        except Exception as e:
            sys_logger.log(f"[Mock Web Server Error] Failed to bind to {self.host}:{self.port}: {e}")
            return
            
        self.server_socket.listen(5)
        self.running = True
        sys_logger.log(f"[Mock Web Server] Started listening on {self.host}:{self.port}")
        
        thread = threading.Thread(target=self._accept_loop, daemon=True)
        thread.start()

    def stop(self):
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        sys_logger.log("[Mock Web Server] Stopped")

    def _accept_loop(self):
        while self.running:
            try:
                client_sock, client_addr = self.server_socket.accept()
                thread = threading.Thread(target=self._handle_request, args=(client_sock,), daemon=True)
                thread.start()
            except OSError:
                break

    def _handle_request(self, client_sock):
        try:
            request_data = client_sock.recv(2048).decode('utf-8', errors='ignore')
            if not request_data:
                client_sock.close()
                return

            lines = request_data.split('\r\n')
            req_line = lines[0]
            parts = req_line.split(' ')
            if len(parts) < 2:
                client_sock.close()
                return
                
            method, path = parts[0], parts[1]
            
            host = "localhost"
            for line in lines:
                if line.lower().startswith('host:'):
                    host_val = line.split(':', 1)[1].strip()
                    host = host_val.split(':')[0]
                    break

            sys_logger.log(f"[Mock Web Server] Request: {method} {host}{path}")

            path = path.split('?')[0]
            
            if path == "/":
                path = "/index.html"
                
            if not os.path.splitext(path)[1]:
                path += ".html"

            filepath = os.path.join(self.web_root, host, path.lstrip('/'))
            filepath = os.path.abspath(filepath)
            
            # Since mock_web is in the project root, and we are in networking_stack,
            # we need to adjust the web_root path resolution.
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            web_root_abs = os.path.join(base_dir, self.web_root)
            filepath = os.path.join(web_root_abs, host, path.lstrip('/'))
            
            if not filepath.startswith(web_root_abs):
                status_code = "403 Forbidden"
                response_body = "<h1>403 Forbidden</h1><p>Access outside web root is forbidden.</p>"
            elif os.path.exists(filepath) and os.path.isfile(filepath):
                status_code = "200 OK"
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        response_body = f.read()
                except Exception as e:
                    status_code = "500 Internal Error"
                    response_body = f"<h1>500 Server Error</h1><p>{str(e)}</p>"
            else:
                status_code = "404 Not Found"
                response_body = f"<h1>404 Not Found</h1><p>File '{path}' not found on host '{host}'.</p>"

            response = (
                f"HTTP/1.1 {status_code}\r\n"
                "Content-Type: text/html; charset=utf-8\r\n"
                f"Content-Length: {len(response_body.encode('utf-8'))}\r\n"
                "Connection: close\r\n\r\n"
                f"{response_body}"
            )
            client_sock.sendall(response.encode('utf-8'))

        except Exception as e:
            sys_logger.log(f"[Mock Web Server Client Error] {e}")
        finally:
            client_sock.close()
