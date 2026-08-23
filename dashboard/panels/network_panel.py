import tkinter as tk
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from dashboard.widgets.status_cards import MetricCard
from dashboard.widgets.charts import LineChart

class NetworkPanel(tk.LabelFrame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, text="Networking Stack", font=("Arial", 10, "bold"), bg="#1e293b", fg="#34d399", padx=10, pady=10, *args, **kwargs)
        
        cards_frame = tk.Frame(self, bg="#1e293b")
        cards_frame.pack(fill="x", pady=(0, 10))
        
        self.sent_card = MetricCard(cards_frame, "Bytes Sent", "0", "B")
        self.sent_card.pack(side="left", fill="x", expand=True, padx=5)
        
        self.recv_card = MetricCard(cards_frame, "Bytes Recv", "0", "B")
        self.recv_card.pack(side="left", fill="x", expand=True, padx=5)
        
        self.conn_card = MetricCard(cards_frame, "Active Conns", "0", "")
        self.conn_card.pack(side="left", fill="x", expand=True, padx=5)
        
        chart_frame = tk.Frame(self, bg="#1e293b")
        chart_frame.pack(fill="x")
        tk.Label(chart_frame, text="Traffic Throughput", font=("Arial", 9), bg="#1e293b", fg="#94a3b8").pack(anchor="w")
        
        self.traffic_chart = LineChart(chart_frame, height=100, fg="#34d399")
        self.traffic_chart.pack(fill="x", pady=5)

    def update_metrics(self, metric):
        if not metric:
            return
        self.sent_card.set_value(metric.bytes_sent)
        self.recv_card.set_value(metric.bytes_recv)
        self.conn_card.set_value(metric.active_connections)
        self.traffic_chart.update_data(metric.bytes_recv)
