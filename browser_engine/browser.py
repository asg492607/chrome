import sys
import os
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from networking_stack.http_client import http_get
from networking_stack.dhcp_server import run_dhcp_client

from browser_engine.browser_window import BrowserWindow
from browser_engine.parsing.dom_builder import DOMBuilder
from browser_engine.styling.cascade_engine import CascadeEngine
from browser_engine.layout.layout_engine import LayoutEngine
from browser_engine.rendering.render_engine import RenderEngine
from browser_engine.asg_protocol_handler import AsgProtocolHandler

class Browser:
    def __init__(self):
        self.window = BrowserWindow(self)
        
        self.dom_builder = DOMBuilder()
        self.cascade_engine = CascadeEngine()
        self.layout_engine = LayoutEngine(canvas_width=720)
        self.render_engine = RenderEngine(self.window)
        
        self.dhcp_config = None
        self.dns_port = 5353
        self.proxy_port = 8282
        self.history = []           # list of {url, timestamp} dicts
        self.history_index = -1
        self.current_url = ""

        # ── asg:// Sovereign Protocol Handler ──────────────────────────────
        # base_dir = mockchrome root (two levels up from browser_engine/)
        _base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        self.asg_handler = AsgProtocolHandler(_base_dir)
        self.asg_handler.set_history_ref(self.history)
        # ──────────────────────────────────────────────────────────────────

        self.window.log_diagnostic("[System] Browser boot complete. Interface offline.")
        self.window.log_diagnostic("[asg://] Sovereign protocol handler registered.")
        self.window.log_diagnostic("[System] Click 'Request DHCP IP' to bind interface to network simulator.")

    def run(self):
        self.window.mainloop()

    def request_dhcp_toggle(self):
        if self.dhcp_config:
            self.release_dhcp()
        else:
            self.request_dhcp()

    def request_dhcp(self):
        self.window.log_diagnostic("[DHCP] Starting DHCP handshake process (DORA)...")
        config = run_dhcp_client(server_port=6767)
        if config:
            self.dhcp_config = config
            self.window.lbl_ip.config(text=f"IP Address: {config['ip']}", fg="#34d399")
            self.window.lbl_gateway.config(text=f"Gateway IP: {config['router']}", fg="#cbd5e1")
            self.window.lbl_dns.config(text=f"DNS Server: {config['dns']}", fg="#cbd5e1")
            self.window.btn_dhcp.config(text="Release IP (Reset)", bg="#ef4444", activebackground="#dc2626")
            self.window.log_diagnostic(f"[DHCP] Handshake Success! Bound to IP: {config['ip']}. Lease expires in {config['lease_time']}s.")
        else:
            self.window.log_diagnostic("[DHCP Error] Server timed out! Verify network server thread is active.")

    def release_dhcp(self):
        self.dhcp_config = None
        self.window.lbl_ip.config(text="IP Address: Unassigned", fg="#94a3b8")
        self.window.lbl_gateway.config(text="Gateway IP: Unassigned", fg="#94a3b8")
        self.window.lbl_dns.config(text="DNS Server: Unassigned", fg="#94a3b8")
        self.window.btn_dhcp.config(text="Request DHCP IP", bg="#10b981", activebackground="#059669")
        self.window.log_diagnostic("[DHCP] Released IP configuration. Interface down.")

    def go_home(self):
        """Navigate to the sovereign ASG World homepage via asg:// protocol."""
        self.navigate("asg://world")

    def refresh(self):
        if self.current_url:
            self.navigate(self.current_url, add_to_history=False)

    def navigate_from_bar(self):
        url = self.window.url_entry.get().strip()
        if url:
            self.navigate(url)

    def navigate(self, url, add_to_history=True):
        url = url.strip()

        # ── asg:// Sovereign Protocol: intercept BEFORE HTTP stack ──────────
        if self.asg_handler.is_asg_url(url):
            self.window.log_diagnostic(f"\n[Browser] asg:// intercept: {url}")
            html, logs = self.asg_handler.resolve(url)
            for line in logs:
                self.window.log_diagnostic(line)

            self.current_url = url
            self.window.url_entry.delete(0, "end")
            self.window.url_entry.insert(0, url)

            if add_to_history:
                if self.history_index < len(self.history) - 1:
                    self.history = self.history[:self.history_index + 1]
                self.history.append({
                    "url": url,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                self.history_index += 1

            self.render_pipeline(html)
            return
        # ───────────────────────────────────────────────────────────────────

        # ── Standard HTTP flow (unchanged) ─────────────────────────────────
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "http://" + url
            
        self.window.log_diagnostic(f"\n[Browser] Navigating to: {url}")
        
        status, headers, body_content, logs = http_get(
            url,
            dhcp_config=self.dhcp_config,
            dns_port=self.dns_port,
            proxy_port=self.proxy_port
        )
        
        for log_line in logs:
            self.window.log_diagnostic(log_line)
            
        if status == "Offline":
            body_content = "<html><body><h1>Offline</h1><p>Your browser is offline. Click 'Request DHCP IP' to connect!</p></body></html>"
            
        self.current_url = url
        self.window.url_entry.delete(0, "end")
        self.window.url_entry.insert(0, url.replace("http://", "").replace("https://", ""))

        if add_to_history:
            if self.history_index < len(self.history) - 1:
                self.history = self.history[:self.history_index + 1]
            self.history.append({
                "url": url,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            self.history_index += 1

        self.render_pipeline(body_content)

    def render_pipeline(self, html_text):
        # 1. Parse HTML to DOM
        dom_root = self.dom_builder.build(html_text)
        
        # 2. Apply and Cascade styling
        self.cascade_engine.apply_styles(dom_root)
        
        # 3. Compute layout box locations
        layout_boxes = self.layout_engine.compute_layout(dom_root)
        
        # 4. Paint to Canvas
        self.render_engine.render(self.window.canvas, layout_boxes)

    def go_back(self):
        if self.history_index > 0:
            self.history_index -= 1
            url = self.history[self.history_index]
            self.navigate(url, add_to_history=False)
            self.window.log_diagnostic(f"[Browser] Moved Back in History to: {url}")

    def go_forward(self):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            url = self.history[self.history_index]
            self.navigate(url, add_to_history=False)
            self.window.log_diagnostic(f"[Browser] Moved Forward in History to: {url}")

if __name__ == "__main__":
    app = Browser()
    app.dhcp_config = {
        "ip": "192.168.1.100",
        "router": "192.168.1.1",
        "dns": "127.0.0.1"
    }
    app.window.lbl_ip.config(text="IP Address: 192.168.1.100 (Mocked)", fg="#34d399")
    app.render_pipeline("<html><body><h1>Welcome to PacketForge</h1><p>This is a custom-written web browser with a multi-stage rendering pipeline.</p></body></html>")
    app.run()
