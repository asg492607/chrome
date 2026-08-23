import os
import sys
import json
import urllib.parse
import urllib.request
import ssl
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

# Ensure parent directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core_platform.logging_system import sys_logger
from networking_stack.dhcp_server import run_dhcp_client
from networking_stack.http_client import http_get
from browser_engine.parsing.dom_builder import DOMBuilder
from browser_engine.styling.cascade_engine import CascadeEngine
from browser_engine.layout.layout_engine import LayoutEngine
from browser_engine.asg_protocol_handler import AsgProtocolHandler
from search_platform.crawler import Crawler
from search_platform.index_builder import IndexBuilder
from search_platform.query_processor import process_query
from search_platform.ranking_engine import RankingEngine
from search_platform.search_config import SearchConfig
from search_platform.search_api import render_search_homepage, render_search_results
from chromium_engine import WebGateway, SearchFederator, ChromiumRuntime


class DashboardServer:
    def __init__(self, host="127.0.0.1", port=8282):
        self.host = host
        self.port = port
        self.running = False
        self.httpd = None
        self.server_thread = None
        
        self.base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        
        # Dedicated Chromium Engine Backend
        self.web_gateway = WebGateway(timeout=12)
        self.search_federator = SearchFederator(self.base_dir)
        self.chromium_runtime = ChromiumRuntime()
        
        # Automatically lease active DHCP configuration
        self.dhcp_config = {
            "ip": "192.168.1.100",
            "subnet": "255.255.255.0",
            "router": "192.168.1.1",
            "dns": "192.168.1.53",
            "lease_time": 86400
        }
        
        # Load index builder internally for search queries
        index_file = os.path.join(self.base_dir, 'search_index.json')
        self.indexer = IndexBuilder(index_file)
        self.indexer.load_index()
        self.ranking_engine = RankingEngine()
        
        # Viewport DOM, style cascade, and layout engines
        self.dom_builder = DOMBuilder()
        self.cascade_engine = CascadeEngine()
        self.layout_engine = LayoutEngine(canvas_width=760)
        
        # Sovereign asg:// protocol handler
        self.asg_handler = AsgProtocolHandler(self.base_dir)
        self.history_records = []
        self.asg_handler.set_history_ref(self.history_records)

    def start(self):
        parent_server = self

        class DashboardHTTPHandler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, format, *args):
                pass

            def do_OPTIONS(self):
                self.send_response(200)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', 'Content-Type')
                self.end_headers()

            def do_GET(self):
                parsed = urllib.parse.urlparse(self.path)
                route = parsed.path
                query_params = urllib.parse.parse_qs(parsed.query)
                host_header = self.headers.get('Host', 'localhost').split(':')[0].lower()

                # Favicon
                if route == "/favicon.ico":
                    self._serve_favicon()
                    return

                # Virtual Host Routing
                if host_header == "myblog.com":
                    self._serve_mock_file("myblog.com", route)
                    return
                elif host_header == "news.com":
                    self._serve_mock_file("news.com", route)
                    return
                elif host_header == "asgsearch.local":
                    self._serve_search(route, query_params)
                    return

                # Localhost Endpoints
                if route.startswith("/api/"):
                    if route == "/api/status":
                        self._api_status()
                    elif route == "/api/logs":
                        self._api_logs()
                    elif route == "/api/index":
                        self._api_index()
                    elif route == "/api/metrics":
                        self._api_metrics()
                    elif route == "/api/search":
                        query = query_params.get("q", [""])[0]
                        res = parent_server.search_federator.search(query)
                        self._send_json(res)
                    elif route == "/api/runtime":
                        self._send_json(parent_server.chromium_runtime.get_runtime_metrics())
                    elif route == "/api/browse":
                        url_list = query_params.get("url", [""])
                        self._api_browse(url_list[0])
                    else:
                        self._send_response("404 Not Found", "text/plain", "API Endpoint not found.")
                
                # Direct Web Pages
                elif route.startswith("/world") or route.startswith("/asg_world"):
                    self._serve_asg_world()
                elif route in ["/settings", "/settings/", "/chrome://settings"]:
                    html, _ = parent_server.asg_handler.resolve("asg://settings")
                    self._send_response("200 OK", "text/html; charset=utf-8", html)
                elif route in ["/history", "/history/", "/chrome://history"]:
                    html, _ = parent_server.asg_handler.resolve("asg://history")
                    self._send_response("200 OK", "text/html; charset=utf-8", html)
                elif route in ["/about", "/about/", "/chrome://about"]:
                    html, _ = parent_server.asg_handler.resolve("asg://about")
                    self._send_response("200 OK", "text/html; charset=utf-8", html)
                elif route.startswith("/blog/"):
                    sub_route = route[5:] if len(route) > 5 else "/"
                    self._serve_mock_file("myblog.com", sub_route)
                elif route.startswith("/news/"):
                    sub_route = route[5:] if len(route) > 5 else "/"
                    self._serve_mock_file("news.com", sub_route)
                elif route.startswith("/search"):
                    self._serve_search(route, query_params)
                elif route == "/proxy":
                    target_url = query_params.get("url", [""])[0]
                    self._serve_proxy(target_url)
                elif route == "/" or route == "/index.html":
                    self._serve_static("index.html")
                else:
                    self._send_response("404 Not Found", "text/html", "<h1>404 Not Found</h1><p>Path not found.</p>")

            def do_OPTIONS(self):
                self.send_response(200)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', '*')
                self.send_header('Access-Control-Max-Age', '86400')
                self.send_header('Content-Length', '0')
                self.end_headers()

            def do_POST(self):
                parsed = urllib.parse.urlparse(self.path)
                route = parsed.path

                if route == "/api/dhcp":
                    self._api_dhcp_request()
                elif route == "/api/dhcp/release":
                    self._api_dhcp_release()
                elif route == "/api/crawl":
                    self._api_crawl()
                else:
                    self._send_response("404 Not Found", "text/plain", "API Endpoint not found.")

            def _serve_favicon(self):
                svg_favicon = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="8" fill="#6366f1"/><text x="16" y="22" fill="white" font-family="sans-serif" font-weight="900" font-size="13" text-anchor="middle">ASG</text></svg>'
                self._send_response("200 OK", "image/svg+xml", svg_favicon)

            def _serve_static(self, filename):
                template_path = os.path.join(os.path.dirname(__file__), 'templates', filename)
                if os.path.exists(template_path):
                    with open(template_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    self._send_response("200 OK", "text/html; charset=utf-8", content)
                else:
                    self._send_response("404 Not Found", "text/plain", f"Template {filename} not found.")

            def _serve_asg_world(self):
                asg_world_path = os.path.join(parent_server.base_dir, 'asg_world', 'index.html')
                if os.path.exists(asg_world_path):
                    with open(asg_world_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    sys_logger.log("[HTTP] 200 OK - Served ASG World Homepage")
                    self._send_response("200 OK", "text/html; charset=utf-8", content)
                else:
                    self._send_response("404 Not Found", "text/plain", "asg_world/index.html not found.")

            def _serve_mock_file(self, domain, route):
                web_root = os.path.join(parent_server.base_dir, 'mock_web')
                if route == "/" or route == "":
                    route = "/index.html"
                if not os.path.splitext(route)[1]:
                    route += ".html"
                    
                filepath = os.path.abspath(os.path.join(web_root, domain, route.lstrip('/')))
                if not filepath.startswith(web_root):
                    sys_logger.log(f"[HTTP] 403 Forbidden - Blocked traversal: {route}")
                    self._send_response("403 Forbidden", "text/html", "<h1>403 Forbidden</h1>")
                    return
                    
                if os.path.exists(filepath) and os.path.isfile(filepath):
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                        sys_logger.log(f"[HTTP] 200 OK - Served {domain}{route}")
                        self._send_response("200 OK", "text/html; charset=utf-8", content)
                    except Exception as e:
                        self._send_response("500 Internal Error", "text/html", f"<h1>500 Server Error</h1><p>{str(e)}</p>")
                else:
                    sys_logger.log(f"[HTTP] 404 Not Found - Missing: {domain}{route}")
                    self._send_response("404 Not Found", "text/html", f"<h1>404 Not Found</h1><p>File '{route}' not found on '{domain}'.</p>")

            def _serve_search(self, route, query_params):
                query_list = query_params.get("q", [""])
                query = query_list[0].strip()
                if query:
                    parent_server.indexer.load_index()
                    query_terms = process_query(query, SearchConfig.STOP_WORDS)
                    results = parent_server.ranking_engine.rank(query_terms, parent_server.indexer.index, parent_server.indexer.documents)
                    body = render_search_results(query, results)
                else:
                    body = render_search_homepage()
                sys_logger.log(f"[HTTP] 200 OK - Served Search Page for '{query if query else 'home'}'")
                self._send_response("200 OK", "text/html; charset=utf-8", body)

            def _serve_proxy(self, target_url):
                status_code, content_type, body_bytes = parent_server.web_gateway.fetch_url(target_url)
                self.send_response(status_code)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(body_bytes)))
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(body_bytes)
                self.wfile.flush()

            def _api_status(self):
                status_data = {
                    "dhcp": "Active" if parent_server.dhcp_config else "Offline",
                    "dns": "Active",
                    "nginx": "Active" if parent_server.running else "Offline",
                    "web_server": "Active" if parent_server.running else "Offline",
                    "search_server": "Active" if parent_server.running else "Offline",
                    "client_ip": parent_server.dhcp_config.get("ip") if parent_server.dhcp_config else "Offline",
                    "lease_details": parent_server.dhcp_config if parent_server.dhcp_config else None,
                    "port": parent_server.port
                }
                self._send_json(status_data)

            def _api_logs(self):
                logs = sys_logger.get_logs()
                self._send_json({"logs": logs})

            def _api_index(self):
                parent_server.indexer.load_index()
                data = {
                    "documents": parent_server.indexer.documents,
                    "index": parent_server.indexer.index
                }
                self._send_json(data)

            def _api_metrics(self):
                parent_server.indexer.load_index()
                metrics = {
                    "documents_indexed": len(parent_server.indexer.documents),
                    "vocabulary_size": len(parent_server.indexer.index),
                    "dhcp_status": "Assigned" if parent_server.dhcp_config else "Unassigned",
                    "server_uptime": "Online",
                    "active_port": parent_server.port
                }
                self._send_json(metrics)

            def _api_dhcp_request(self):
                sys_logger.log("[DHCP] Starting simulated DHCP DORA handshake...")
                sys_logger.log("[DHCP] Received DISCOVER (UDP broadcast 255.255.255.255:67)")
                client_ip = "192.168.1.100"
                sys_logger.log(f"[DHCP] Sent OFFER {client_ip} (DNS: 192.168.1.53, Router: 192.168.1.1)")
                sys_logger.log(f"[DHCP] Received REQUEST for {client_ip}")
                sys_logger.log(f"[DHCP] Sent ACK. Configuration leased successfully!")
                
                parent_server.dhcp_config = {
                    "ip": client_ip,
                    "subnet": "255.255.255.0",
                    "router": "192.168.1.1",
                    "dns": "192.168.1.53",
                    "lease_time": 86400
                }
                self._send_json({"status": "success", "config": parent_server.dhcp_config})

            def _api_dhcp_release(self):
                sys_logger.log("[DHCP] Releasing DHCP leased address 192.168.1.100. Interface down.")
                parent_server.dhcp_config = None
                self._send_json({"status": "success"})

            def _api_crawl(self):
                sys_logger.log("[Crawler] Crawl triggered via unified dashboard.")
                try:
                    mock_web_dir = os.path.join(parent_server.base_dir, 'mock_web')
                    crawler = Crawler(mock_web_dir)
                    pages = crawler.crawl()
                    parent_server.indexer.build_index(pages)
                    parent_server.indexer.load_index()
                    
                    sys_logger.log(f"[Crawler] Successfully crawled {len(pages)} pages. Indexed {len(parent_server.indexer.index)} terms.")
                    self._send_json({
                        "status": "success",
                        "pages_crawled": len(pages),
                        "terms_indexed": len(parent_server.indexer.index)
                    })
                except Exception as e:
                    sys_logger.log(f"[Crawler Error] Re-indexing failed: {e}")
                    self._send_json({"status": "failed", "error": str(e)}, status_code=500)

            def _api_browse(self, url):
                if not url:
                    self._send_json({"error": "Missing URL parameter"}, status_code=400)
                    return
                    
                sys_logger.log(f"[Browser Viewport] Processing navigation request: {url}")
                status = "200 OK"
                headers = {"content-type": "text/html"}
                body_content = ""
                logs = []
                
                if parent_server.asg_handler.is_asg_url(url):
                    logs.append(f"[Browser] Sovereign asg:// protocol intercept: {url}")
                    body_content, asg_logs = parent_server.asg_handler.resolve(url)
                    logs.extend(asg_logs)
                else:
                    if not parent_server.dhcp_config:
                        status = "Offline"
                        body_content = "<html><body><h1>Interface Offline</h1><p>Request DHCP IP lease first.</p></body></html>"
                    else:
                        status, headers, body_content, http_logs = http_get(
                            url,
                            dhcp_config=parent_server.dhcp_config,
                            dns_port=5353,
                            proxy_port=parent_server.port
                        )
                        logs.extend(http_logs)
                
                layout_boxes_data = []
                if status != "Offline" and not status.startswith("CONNECTION_FAILED") and not status.startswith("DNS_ERROR"):
                    try:
                        dom_root = parent_server.dom_builder.build(body_content)
                        parent_server.cascade_engine.apply_styles(dom_root)
                        boxes = parent_server.layout_engine.compute_layout(dom_root)
                        for box in boxes:
                            layout_boxes_data.append({
                                "box_type": box.box_type,
                                "x": box.x,
                                "y": box.y,
                                "w": box.w,
                                "h": box.h,
                                "text": box.text,
                                "style": {
                                    "color": box.style.get("color", "#cbd5e1"),
                                    "background-color": box.style.get("background-color", "transparent"),
                                    "font-size": box.style.get("font-size", "14px"),
                                    "font-weight": box.style.get("font-weight", "normal"),
                                    "font-style": box.style.get("font-style", "normal"),
                                    "font-family": box.style.get("font-family", "Arial"),
                                    "link_url": box.style.get("link_url", None)
                                }
                            })
                    except Exception as le:
                        sys_logger.log(f"[Layout Engine Error] Compile layout failed: {le}")
                
                self._send_json({
                    "status": status,
                    "headers": headers,
                    "raw_html": body_content,
                    "logs": logs,
                    "layout_boxes": layout_boxes_data
                })

            def _send_response(self, status, content_type, body):
                status_code = int(status.split()[0]) if status.split()[0].isdigit() else 200
                response_bytes = body.encode('utf-8') if isinstance(body, str) else body
                
                self.send_response(status_code)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(response_bytes)))
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', 'Content-Type')
                self.end_headers()
                self.wfile.write(response_bytes)
                self.wfile.flush()

            def _send_json(self, data, status_code=200):
                body = json.dumps(data).encode('utf-8')
                self.send_response(status_code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(body)
                self.wfile.flush()

        try:
            self.httpd = ThreadingHTTPServer((self.host, self.port), DashboardHTTPHandler)
            self.running = True
            sys_logger.log(f"[Dashboard Server] Started on http://{self.host}:{self.port}")
            self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
            self.server_thread.start()
            return True
        except Exception as e:
            sys_logger.log(f"[Dashboard Server Error] Failed to bind to {self.host}:{self.port}: {e}")
            return False

    def stop(self):
        self.running = False
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                pass
        sys_logger.log("[Dashboard Server] Stopped")


if __name__ == "__main__":
    server = DashboardServer()
    server.start()
    
    import time
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
