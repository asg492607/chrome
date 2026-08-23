"""
Web Performance Timeline & Resource Timing API Engine.
Implements W3C Performance Timeline Level 2 specification (performance.mark, performance.measure),
High-Resolution Time (performance.now), Navigation Timing Level 2, Resource Timing Level 2, and PerformanceObserver.
"""

import sys
import os
import time
from typing import Dict, List, Optional, Tuple, Any, Callable

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class PerformanceEntry:
    """Base W3C PerformanceEntry class."""

    def __init__(self, name: str, entry_type: str, start_time: float, duration: float):
        self.name = name
        self.entryType = entry_type
        self.startTime = start_time
        self.duration = duration

    def toJSON(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "entryType": self.entryType,
            "startTime": self.startTime,
            "duration": self.duration
        }

    def __repr__(self) -> str:
        return f"PerformanceEntry({self.name}, type={self.entryType}, start={self.startTime:.2f}ms, duration={self.duration:.2f}ms)"


class PerformanceMark(PerformanceEntry):
    """User timing mark performance entry."""

    def __init__(self, name: str, start_time: float):
        super().__init__(name, "mark", start_time, 0.0)


class PerformanceMeasure(PerformanceEntry):
    """User timing measure performance entry."""

    def __init__(self, name: str, start_time: float, duration: float):
        super().__init__(name, "measure", start_time, duration)


class PerformanceNavigationTiming(PerformanceEntry):
    """Navigation timing performance entry tracking page load milestones."""

    def __init__(self, name: str, start_time: float, duration: float):
        super().__init__(name, "navigation", start_time, duration)
        self.fetchStart = start_time
        self.domainLookupStart = start_time + 1.2
        self.domainLookupEnd = start_time + 3.5
        self.connectStart = start_time + 3.8
        self.connectEnd = start_time + 8.1
        self.requestStart = start_time + 8.5
        self.responseStart = start_time + 12.0
        self.responseEnd = start_time + 18.5
        self.domInteractive = start_time + 25.0
        self.domComplete = start_time + 40.0
        self.loadEventEnd = start_time + 42.5


class PerformanceResourceTiming(PerformanceEntry):
    """Resource timing performance entry tracking resource fetches."""

    def __init__(
        self,
        name: str,
        start_time: float,
        duration: float,
        initiator_type: str = "script",
        transfer_size: int = 1024
    ):
        super().__init__(name, "resource", start_time, duration)
        self.initiatorType = initiator_type
        self.transferSize = transfer_size
        self.encodedBodySize = transfer_size
        self.decodedBodySize = transfer_size * 2


class PerformanceObserver:
    """W3C PerformanceObserver listening for reactive performance entry dispatches."""

    def __init__(self, callback: Callable[[List[PerformanceEntry]], None]):
        self.callback = callback
        self.entry_types: List[str] = []
        self.active = False

    def observe(self, entry_types: List[str]) -> None:
        """Starts observing designated performance entry types."""
        self.entry_types = entry_types
        self.active = True

    def disconnect(self) -> None:
        """Stops observing dispatches."""
        self.active = False

    def notify(self, entries: List[PerformanceEntry]) -> None:
        """Delivers matching entries to callback if observer is active."""
        if not self.active:
            return
        matching = [e for e in entries if e.entryType in self.entry_types]
        if matching:
            self.callback(matching)


class PerformanceTimelineEngine:
    """W3C Performance Timeline & High-Resolution Time Engine."""

    def __init__(self):
        self._start_time = time.perf_counter()
        self.entries: List[PerformanceEntry] = []
        self.observers: List[PerformanceObserver] = []
        self.marks: Dict[str, float] = {}

    def now(self) -> float:
        """Returns high-resolution elapsed time in milliseconds."""
        return (time.perf_counter() - self._start_time) * 1000.0

    def mark(self, name: str) -> PerformanceMark:
        """Creates and records a PerformanceMark timestamp."""
        t = self.now()
        self.marks[name] = t
        entry = PerformanceMark(name, t)
        self.entries.append(entry)
        self._notify_observers([entry])
        return entry

    def measure(self, name: str, start_mark: str, end_mark: Optional[str] = None) -> PerformanceMeasure:
        """Calculates duration between two marks and creates a PerformanceMeasure entry."""
        t_start = self.marks.get(start_mark, 0.0)
        t_end = self.marks.get(end_mark, self.now()) if end_mark else self.now()
        duration = max(0.0, t_end - t_start)
        entry = PerformanceMeasure(name, t_start, duration)
        self.entries.append(entry)
        self._notify_observers([entry])
        return entry

    def add_resource_timing(
        self,
        name: str,
        initiator_type: str = "script",
        transfer_size: int = 1024,
        duration: float = 5.0
    ) -> PerformanceResourceTiming:
        """Records a PerformanceResourceTiming entry."""
        t = self.now()
        entry = PerformanceResourceTiming(name, t, duration, initiator_type, transfer_size)
        self.entries.append(entry)
        self._notify_observers([entry])
        return entry

    def add_observer(self, observer: PerformanceObserver) -> None:
        """Registers a PerformanceObserver."""
        if observer not in self.observers:
            self.observers.append(observer)

    def _notify_observers(self, new_entries: List[PerformanceEntry]) -> None:
        """Dispatches new performance entries to active observers."""
        for obs in self.observers:
            obs.notify(new_entries)

    def getEntries(self) -> List[PerformanceEntry]:
        return list(self.entries)

    def getEntriesByType(self, type_name: str) -> List[PerformanceEntry]:
        return [e for e in self.entries if e.entryType == type_name]

    def getEntriesByName(self, name: str) -> List[PerformanceEntry]:
        return [e for e in self.entries if e.name == name]
