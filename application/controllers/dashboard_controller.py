import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from dashboard.dashboard import DashboardApp
from application.events import event_bus, Events

class DashboardController:
    """
    Public interface for controlling the Dashboard UI.
    """
    def __init__(self):
        self.dashboard_app = None

    def initialize(self):
        self.dashboard_app = DashboardApp()
        
        # Subscribe to logging events
        event_bus.subscribe(Events.SYSTEM_STARTUP, lambda: self.log_event("SYSTEM", "INFO", "Platform Booting..."))
        event_bus.subscribe(Events.PROXY_CONNECTED, lambda: self.log_event("NETWORK", "INFO", "Reverse Proxy Online"))
        event_bus.subscribe(Events.DHCP_ASSIGNED, lambda cfg: self.log_event("DHCP", "INFO", f"IP {cfg['ip']} Assigned"))
        event_bus.subscribe(Events.PAGE_LOADED, lambda url: self.log_event("BROWSER", "INFO", f"Navigating to {url}"))
        event_bus.subscribe(Events.INDEX_UPDATED, lambda cnt: self.log_event("SEARCH", "INFO", f"Indexed {cnt} documents"))

    def start_ui(self):
        if self.dashboard_app:
            self.dashboard_app.mainloop()

    def log_event(self, source, level, message):
        if self.dashboard_app:
            self.dashboard_app.log_event(source, level, message)

    def refresh(self):
        if self.dashboard_app:
            self.dashboard_app.refresh_ui()

    def update_network_metrics(self, sent, recv, conns):
        if self.dashboard_app:
            self.dashboard_app.network_collector.record_traffic(sent, recv, conns)
            self.refresh()
            
    def update_browser_metrics(self, load_ms, nodes, render_ms):
        if self.dashboard_app:
            self.dashboard_app.browser_collector.record_load(load_ms, nodes, render_ms)
            self.refresh()
