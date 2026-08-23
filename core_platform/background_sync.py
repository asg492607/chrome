"""
Background Sync & Periodic Background Sync Engine.
Implements W3C Web Background Sync API (SyncManager) and Periodic Background Sync API (PeriodicSyncManager) specifications,
network connectivity detection triggers, and ServiceWorker sync/periodicsync background event dispatches.
"""

import sys
import os
import time
from typing import Dict, List, Optional, Tuple, Any, Union

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class SyncRegistration:
    """Record holding state for one-off background sync registration."""

    def __init__(self, tag: str, registered_at: float):
        self.tag = tag
        self.registered_at = registered_at
        self.status = "pending" # "pending" or "completed"


class PeriodicSyncRegistration:
    """Record holding state for periodic background sync registration."""

    def __init__(self, tag: str, min_interval: int, registered_at: float):
        self.tag = tag
        self.min_interval = min_interval # in milliseconds
        self.registered_at = registered_at
        self.last_sync = 0.0


class BackgroundSyncEngine:
    """Core Background Sync & Periodic Sync Task Dispatcher."""

    _sync_tags: Dict[str, SyncRegistration] = {}
    _pending_queue: List[str] = []
    _periodic_tags: Dict[str, PeriodicSyncRegistration] = {}
    _is_online: bool = True

    @classmethod
    def register_sync(cls, tag: str) -> bool:
        """Registers a one-off background sync task tag."""
        cls._sync_tags[tag] = SyncRegistration(tag, time.time())
        cls._pending_queue.append(tag)
        return True

    @classmethod
    def register_periodic_sync(cls, tag: str, min_interval: int) -> bool:
        """Registers a periodic background sync task tag with minInterval in ms."""
        cls._periodic_tags[tag] = PeriodicSyncRegistration(tag, min_interval, time.time())
        return True

    @classmethod
    def unregister_periodic_sync(cls, tag: str) -> bool:
        """Unregisters a periodic sync task tag."""
        if tag in cls._periodic_tags:
            del cls._periodic_tags[tag]
            return True
        return False

    @classmethod
    def on_network_online(cls) -> List[Dict[str, Any]]:
        """Triggered on network connectivity restoration to fire pending sync events into ServiceWorker."""
        cls._is_online = True
        dispatched_events = []
        pending = cls._pending_queue
        cls._pending_queue = []

        for tag in pending:
            if tag in cls._sync_tags:
                reg = cls._sync_tags[tag]
                if reg.status == "pending":
                    reg.status = "completed"
                    dispatched_events.append({
                        "type": "sync",
                        "tag": tag,
                        "lastChance": False
                    })

        return dispatched_events

    @classmethod
    def on_network_offline(cls) -> None:
        """Triggered on network offline state transition."""
        cls._is_online = False

    @classmethod
    def trigger_periodic_sync(cls, tag: Optional[str] = None) -> List[Dict[str, Any]]:
        """Triggers periodic background sync task dispatches."""
        dispatched_events = []

        if tag:
            if tag in cls._periodic_tags:
                reg = cls._periodic_tags[tag]
                reg.last_sync = time.time()
                dispatched_events.append({
                    "type": "periodicsync",
                    "tag": tag
                })
        else:
            for p_tag, reg in cls._periodic_tags.items():
                reg.last_sync = time.time()
                dispatched_events.append({
                    "type": "periodicsync",
                    "tag": p_tag
                })

        return dispatched_events

    @classmethod
    def get_sync_tags(cls) -> List[str]:
        """Returns list of all active sync tags."""
        return [tag for tag, reg in cls._sync_tags.items() if reg.status == "pending"]

    @classmethod
    def get_periodic_tags(cls) -> List[str]:
        """Returns list of all registered periodic sync tags."""
        return list(cls._periodic_tags.keys())

    @classmethod
    def clear_all(cls) -> None:
        """Clears all background sync registrations."""
        cls._sync_tags.clear()
        cls._pending_queue.clear()
        cls._periodic_tags.clear()
        cls._is_online = True



class SyncManager:
    """W3C SyncManager navigator.serviceWorker.sync entry point."""

    def __init__(self):
        pass

    def register(self, tag: str) -> bool:
        """Registers a one-off background sync task."""
        if not tag or not isinstance(tag, str):
            raise TypeError("TypeError: Tag must be a non-empty string.")
        return BackgroundSyncEngine.register_sync(tag)

    def getTags(self) -> List[str]:
        """Queries all pending sync tags."""
        return BackgroundSyncEngine.get_sync_tags()


class PeriodicSyncManager:
    """W3C PeriodicSyncManager navigator.serviceWorker.periodicSync entry point."""

    def __init__(self):
        pass

    def register(self, tag: str, options: Optional[Dict[str, Any]] = None) -> bool:
        """Registers a periodic background sync task with minInterval option."""
        if not tag or not isinstance(tag, str):
            raise TypeError("TypeError: Tag must be a non-empty string.")
        opts = options or {}
        min_interval = opts.get("minInterval", 86400000)
        return BackgroundSyncEngine.register_periodic_sync(tag, min_interval)

    def getTags(self) -> List[str]:
        """Queries all registered periodic sync tags."""
        return BackgroundSyncEngine.get_periodic_tags()

    def unregister(self, tag: str) -> bool:
        """Unregisters a periodic sync task."""
        return BackgroundSyncEngine.unregister_periodic_sync(tag)
