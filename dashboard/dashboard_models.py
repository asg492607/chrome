from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class NetworkMetric:
    timestamp: float
    bytes_sent: int = 0
    bytes_recv: int = 0
    active_connections: int = 0

@dataclass
class BrowserMetric:
    timestamp: float
    page_load_ms: float = 0
    dom_nodes_count: int = 0
    render_time_ms: float = 0

@dataclass
class SearchMetric:
    timestamp: float
    queries_processed: int = 0
    average_latency_ms: float = 0
    index_size: int = 0

@dataclass
class EventLog:
    timestamp: float
    source: str
    level: str
    message: str
