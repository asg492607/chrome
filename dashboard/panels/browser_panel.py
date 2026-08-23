import tkinter as tk
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from dashboard.widgets.status_cards import MetricCard
from dashboard.widgets.charts import LineChart

class BrowserPanel(tk.LabelFrame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, text="Browser Engine", font=("Arial", 10, "bold"), bg="#1e293b", fg="#818cf8", padx=10, pady=10, *args, **kwargs)
        
        # Cards Frame
        cards_frame = tk.Frame(self, bg="#1e293b")
        cards_frame.pack(fill="x", pady=(0, 10))
        
        self.load_card = MetricCard(cards_frame, "Page Load Time", "0", "ms")
        self.load_card.pack(side="left", fill="x", expand=True, padx=5)
        
        self.nodes_card = MetricCard(cards_frame, "DOM Nodes", "0", "")
        self.nodes_card.pack(side="left", fill="x", expand=True, padx=5)
        
        self.render_card = MetricCard(cards_frame, "Render Time", "0", "ms")
        self.render_card.pack(side="left", fill="x", expand=True, padx=5)
        
        # Chart
        chart_frame = tk.Frame(self, bg="#1e293b")
        chart_frame.pack(fill="x")
        tk.Label(chart_frame, text="Load Time Trend", font=("Arial", 9), bg="#1e293b", fg="#94a3b8").pack(anchor="w")
        
        self.load_chart = LineChart(chart_frame, height=100, fg="#818cf8")
        self.load_chart.pack(fill="x", pady=5)

    def update_metrics(self, metric):
        if not metric:
            return
        self.load_card.set_value(f"{metric.page_load_ms:.1f}")
        self.nodes_card.set_value(metric.dom_nodes_count)
        self.render_card.set_value(f"{metric.render_time_ms:.1f}")
        self.load_chart.update_data(metric.page_load_ms)
