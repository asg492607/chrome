import tkinter as tk
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from dashboard.widgets.indicators import StatusIndicator

class TelemetryPanel(tk.LabelFrame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, text="System Telemetry", font=("Arial", 10, "bold"), bg="#1e293b", fg="#e2e8f0", padx=10, pady=10, *args, **kwargs)
        
        self.dhcp_ind = StatusIndicator(self, "DHCP Server", "Offline")
        self.dhcp_ind.pack(fill="x", pady=2)
        
        self.dns_ind = StatusIndicator(self, "DNS Server", "Offline")
        self.dns_ind.pack(fill="x", pady=2)
        
        self.proxy_ind = StatusIndicator(self, "Reverse Proxy", "Offline")
        self.proxy_ind.pack(fill="x", pady=2)
        
        self.search_ind = StatusIndicator(self, "Search API", "Offline")
        self.search_ind.pack(fill="x", pady=2)

    def set_system_status(self, dhcp, dns, proxy, search):
        self.dhcp_ind.set_status(dhcp)
        self.dns_ind.set_status(dns)
        self.proxy_ind.set_status(proxy)
        self.search_ind.set_status(search)
