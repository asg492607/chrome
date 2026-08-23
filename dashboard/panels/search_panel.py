import tkinter as tk
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from dashboard.widgets.status_cards import MetricCard
from dashboard.widgets.charts import LineChart

class SearchPanel(tk.LabelFrame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, text="Search Platform", font=("Arial", 10, "bold"), bg="#1e293b", fg="#f472b6", padx=10, pady=10, *args, **kwargs)
        
        cards_frame = tk.Frame(self, bg="#1e293b")
        cards_frame.pack(fill="x", pady=(0, 10))
        
        self.query_card = MetricCard(cards_frame, "Total Queries", "0", "")
        self.query_card.pack(side="left", fill="x", expand=True, padx=5)
        
        self.latency_card = MetricCard(cards_frame, "Avg Latency", "0", "ms")
        self.latency_card.pack(side="left", fill="x", expand=True, padx=5)
        
        self.index_card = MetricCard(cards_frame, "Index Size", "0", "docs")
        self.index_card.pack(side="left", fill="x", expand=True, padx=5)

        chart_frame = tk.Frame(self, bg="#1e293b")
        chart_frame.pack(fill="x")
        tk.Label(chart_frame, text="Query Latency", font=("Arial", 9), bg="#1e293b", fg="#94a3b8").pack(anchor="w")
        
        self.latency_chart = LineChart(chart_frame, height=100, fg="#f472b6")
        self.latency_chart.pack(fill="x", pady=5)

    def update_metrics(self, metric):
        if not metric:
            return
        self.query_card.set_value(metric.queries_processed)
        self.latency_card.set_value(f"{metric.average_latency_ms:.1f}")
        self.index_card.set_value(metric.index_size)
        self.latency_chart.update_data(metric.average_latency_ms)
