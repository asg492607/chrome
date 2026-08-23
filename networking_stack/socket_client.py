import socket

def send_tcp_request(host, port, request_bytes, timeout=4.0):
    """
    Handles raw TCP socket communication.
    Returns (response_bytes, logs)
    """
    logs = []
    client_sock = None
    try:
        logs.append(f"[TCP Connection] Establishing 3-Way Handshake with Server on {host}:{port}...")
        client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_sock.settimeout(timeout)
        
        client_sock.connect((host, port))
        logs.append("[TCP Connection] Connection established. Sending data...")
        
        client_sock.sendall(request_bytes)
        
        response_bytes = b""
        while True:
            chunk = client_sock.recv(4096)
            if not chunk:
                break
            response_bytes += chunk
            
        logs.append(f"[TCP] Received {len(response_bytes)} bytes. Closing connection...")
        return response_bytes, logs
        
    except socket.timeout:
        logs.append(f"[Network Timeout] Failed to connect to host {host} within timeout limit.")
        raise
    except Exception as e:
        logs.append(f"[Network Error] Connection failed: {e}")
        raise
    finally:
        if client_sock:
            try:
                client_sock.close()
            except:
                pass
