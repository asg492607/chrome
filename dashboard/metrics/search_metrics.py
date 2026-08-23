import time
from dashboard.dashboard_models import SearchMetric

class SearchMetricsCollector:
    def __init__(self):
        self.history = []

    def record_query(self, latency, index_size):
        prev_queries = self.get_latest().queries_processed if self.history else 0
        metric = SearchMetric(
            timestamp=time.time(),
            queries_processed=prev_queries + 1,
            average_latency_ms=latency,
            index_size=index_size
        )
        self.history.append(metric)

    def get_latest(self):
        return self.history[-1] if self.history else None
