import urllib.parse
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from networking_stack.dns_server import resolve_dns
from networking_stack.socket_client import send_tcp_request

def http_get(url, dhcp_config=None, dns_port=5353, proxy_port=8282):
    """
    Separated HTTP logic from raw socket handling.
    """
    logs = []
    
    if not dhcp_config:
        logs.append("[Network Error] Client does not have an active IP address! DHCP configuration missing. Boot interface first.")
        return "Offline", {}, "<h1>No Connection</h1><p>Ensure DHCP interface is up.</p>", logs
    
    logs.append(f"[Network] DHCP Lease active. IP: {dhcp_config['ip']}, Gateway: {dhcp_config['router']}, DNS Server: {dhcp_config['dns']}")

    try:
        parsed_url = urllib.parse.urlparse(url)
        scheme = parsed_url.scheme
        if scheme != "http":
            url = "http://" + url
            parsed_url = urllib.parse.urlparse(url)
            
        host = parsed_url.netloc
        path = parsed_url.path if parsed_url.path else "/"
        if parsed_url.query:
            path += "?" + parsed_url.query
            
        host_parts = host.split(":")
        domain = host_parts[0]
        
        logs.append(f"[DNS Lookup] Requesting resolution for domain '{domain}' via DNS server {dhcp_config['dns']}:{dns_port}...")
        
        try:
            server_ip = resolve_dns(domain, dns_server_host="127.0.0.1", dns_server_port=dns_port)
        except Exception as dns_err:
            logs.append(f"[DNS Client Warning] UDP DNS query failed: {dns_err}. Searching local resolver cache...")
            server_ip = None
            
        if not server_ip:
            static_records = {
                "asgsearch.local": "127.0.0.1",
                "asgworld.local":  "127.0.0.1",
                "myblog.com": "127.0.0.1",
                "news.com": "127.0.0.1",
                "localhost": "127.0.0.1"
            }
            server_ip = static_records.get(domain)
            if server_ip:
                logs.append(f"[DNS Success] Resolved '{domain}' -> IP {server_ip} (Simulated Local Cache)")
            else:
                logs.append(f"[DNS Error] DNS resolution failed for domain: '{domain}'")
                return "DNS_ERROR", {}, f"<h1>Address Not Found</h1><p>DNS resolution failed for {domain}. Check your network configuration.</p>", logs
        else:
            logs.append(f"[DNS Success] Resolved '{domain}' -> IP {server_ip}")

        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {domain}\r\n"
            "User-Agent: AsgBrowser/1.0 (ScratchBuilt)\r\n"
            "Accept: text/html\r\n"
            "Connection: close\r\n\r\n"
        )
        
        # Call separated socket_client
        response_bytes, tcp_logs = send_tcp_request("127.0.0.1", proxy_port, request.encode('utf-8'))
        logs.extend(tcp_logs)
        
        if not response_bytes:
            return "EMPTY_RESPONSE", {}, "<h1>Empty Response</h1><p>Server returned no content.</p>", logs
            
        parts = response_bytes.split(b"\r\n\r\n", 1)
        header_part = parts[0].decode('utf-8', errors='ignore')
        body_part = parts[1].decode('utf-8', errors='ignore') if len(parts) > 1 else ""
        
        header_lines = header_part.split("\r\n")
        status_line = header_lines[0]
        
        status_parts = status_line.split(" ", 2)
        status_code = status_parts[1] if len(status_parts) > 1 else "Unknown"
        status_msg = status_parts[2] if len(status_parts) > 2 else ""
        
        logs.append(f"[HTTP Response] Status: {status_line}")
        
        headers = {}
        for line in header_lines[1:]:
            if ":" in line:
                key, val = line.split(":", 1)
                headers[key.strip().lower()] = val.strip()
                
        return f"{status_code} {status_msg}", headers, body_part, logs
        
    except Exception as e:
        logs.append(f"[Network Error] Connection failed: {e}")
        return "CONNECTION_FAILED", {}, f"<h1>Unable to Connect</h1><p>The network simulator encountered an error: {str(e)}</p>", logs
