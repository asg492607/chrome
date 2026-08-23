"""
chromium_engine/chromium_runtime.py
==========================================================================
Chromium Runtime Subsystem

Encapsulates browser session lifecycle, tab management, bookmarks,
navigation history, and DevTools telemetry metrics.
==========================================================================
"""

import time
from typing import List, Dict, Any, Optional
from core_platform.logging_system import sys_logger


class ChromiumTab:
    def __init__(self, tab_id: int, url: str = "asg://world", title: str = "ASG World"):
        self.tab_id = tab_id
        self.url = url
        self.title = title
        self.history = [url]
        self.history_idx = 0
        self.created_at = time.time()

    def navigate(self, url: str, title: Optional[str] = None):
        if self.history_idx < len(self.history) - 1:
            self.history = self.history[:self.history_idx + 1]
        self.history.append(url)
        self.history_idx += 1
        self.url = url
        if title:
            self.title = title

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.tab_id,
            "url": self.url,
            "title": self.title,
            "history_length": len(self.history),
            "current_index": self.history_idx
        }


class ChromiumRuntime:
    """Manages tabs, history, bookmarks, and runtime diagnostics for ASG World Chromium."""

    def __init__(self):
        self.tabs: Dict[int, ChromiumTab] = {}
        self.active_tab_id: Optional[int] = None
        self.next_tab_id = 1
        self.bookmarks: List[Dict[str, str]] = [
            {"title": "ASG World", "url": "asg://world", "icon": "🌐"},
            {"title": "The Packet Hacker Blog", "url": "/blog/", "icon": "📝"},
            {"title": "Global Tech News", "url": "/news/", "icon": "📰"},
            {"title": "Phase II Search", "url": "/world?q=phase2", "icon": "🚀"},
            {"title": "Wikipedia", "url": "/proxy?url=https://en.wikipedia.org", "icon": "🌐"},
            {"title": "Python.org", "url": "/proxy?url=https://www.python.org", "icon": "🐍"},
            {"title": "Settings", "url": "/settings", "icon": "⚙️"}
        ]
        self.history: List[Dict[str, Any]] = []

    def create_tab(self, url: str = "asg://world", title: str = "ASG World") -> ChromiumTab:
        tab_id = self.next_tab_id
        self.next_tab_id += 1
        tab = ChromiumTab(tab_id, url, title)
        self.tabs[tab_id] = tab
        self.active_tab_id = tab_id
        self.record_history(url, title)
        return tab

    def close_tab(self, tab_id: int):
        if tab_id in self.tabs:
            del self.tabs[tab_id]
            if self.active_tab_id == tab_id:
                self.active_tab_id = next(iter(self.tabs.keys())) if self.tabs else None

    def record_history(self, url: str, title: str):
        self.history.insert(0, {
            "url": url,
            "title": title,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        if len(self.history) > 200:
            self.history.pop()

    def get_runtime_metrics(self) -> Dict[str, Any]:
        return {
            "engine": "Chromium Sovereign Runtime 2.0",
            "open_tabs": len(self.tabs),
            "bookmarks_count": len(self.bookmarks),
            "history_entries": len(self.history),
            "status": "Online",
            "dual_search": "Enabled (Internal Priority + Live External Web)"
        }
