import tkinter as tk
from tkinter import ttk
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from dashboard.metrics.browser_metrics import BrowserMetricsCollector
from dashboard.metrics.network_metrics import NetworkMetricsCollector
from dashboard.metrics.search_metrics import SearchMetricsCollector
from dashboard.panels.browser_panel import BrowserPanel
from dashboard.panels.network_panel import NetworkPanel
from dashboard.panels.search_panel import SearchPanel
from dashboard.panels.telemetry_panel import TelemetryPanel
from dashboard.panels.event_log_panel import EventLogPanel

class DashboardApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PacketForge - System Dashboard")
        self.geometry("1200x800")
        self.configure(bg="#0f172a")
        
        # Metrics Collectors
        self.browser_collector = BrowserMetricsCollector()
        self.network_collector = NetworkMetricsCollector()
        self.search_collector = SearchMetricsCollector()

        self._build_ui()

    def _build_ui(self):
        header = tk.Label(self, text="PacketForge Dashboard", font=("Arial", 16, "bold"), bg="#0f172a", fg="#ffffff")
        header.pack(pady=10)

        main_frame = tk.Frame(self, bg="#0f172a")
        main_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # Left Column: Telemetry & Logs
        left_col = tk.Frame(main_frame, bg="#0f172a")
        left_col.pack(side="left", fill="y", expand=False, padx=(0, 10))

        self.telemetry_panel = TelemetryPanel(left_col)
        self.telemetry_panel.pack(fill="x", pady=(0, 10))

        self.event_log = EventLogPanel(left_col)
        self.event_log.pack(fill="both", expand=True)

        # Right Column: Subsystem Metrics
        right_col = tk.Frame(main_frame, bg="#0f172a")
        right_col.pack(side="left", fill="both", expand=True)

        self.network_panel = NetworkPanel(right_col)
        self.network_panel.pack(fill="x", pady=(0, 10))

        self.search_panel = SearchPanel(right_col)
        self.search_panel.pack(fill="x", pady=(0, 10))

        self.browser_panel = BrowserPanel(right_col)
        self.browser_panel.pack(fill="x", pady=(0, 10))

    def log_event(self, source, level, message):
        formatted = f"[{source}] [{level}] {message}"
        self.event_log.log(formatted)

    def refresh_ui(self):
        self.browser_panel.update_metrics(self.browser_collector.get_latest())
        self.network_panel.update_metrics(self.network_collector.get_latest())
        self.search_panel.update_metrics(self.search_collector.get_latest())

if __name__ == "__main__":
    app = DashboardApp()
    app.telemetry_panel.set_system_status("Online", "Online", "Online", "Offline")
    app.log_event("SYSTEM", "INFO", "Dashboard initialized.")
    app.log_event("NETWORK", "WARN", "High latency detected on gateway.")
    
    # Mock data injection
    app.network_collector.record_traffic(sent=1024, recv=2048, conns=5)
    app.search_collector.record_query(latency=45.2, index_size=1500)
    app.browser_collector.record_load(load_ms=120.5, nodes_count=45, render_ms=15.2)
    app.refresh_ui()
    
    app.mainloop()
