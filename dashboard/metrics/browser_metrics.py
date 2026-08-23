import time
from dashboard.dashboard_models import BrowserMetric

class BrowserMetricsCollector:
    def __init__(self):
        self.history = []

    def record_load(self, load_ms, nodes_count, render_ms):
        metric = BrowserMetric(
            timestamp=time.time(),
            page_load_ms=load_ms,
            dom_nodes_count=nodes_count,
            render_time_ms=render_ms
        )
        self.history.append(metric)

    def get_latest(self):
        return self.history[-1] if self.history else None
