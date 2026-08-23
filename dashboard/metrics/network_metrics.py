import time
from dashboard.dashboard_models import NetworkMetric

class NetworkMetricsCollector:
    def __init__(self):
        self.history = []

    def record_traffic(self, sent, recv, conns):
        metric = NetworkMetric(
            timestamp=time.time(),
            bytes_sent=sent,
            bytes_recv=recv,
            active_connections=conns
        )
        self.history.append(metric)

    def get_latest(self):
        return self.history[-1] if self.history else None
