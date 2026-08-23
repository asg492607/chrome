"""
Web Locks API & Cross-Tab Resource Synchronization Engine.
Implements W3C Web Locks API specification (navigator.locks.request, navigator.locks.query),
exclusive vs shared lock modes, FIFO queue ordering, ifAvailable non-blocking requests, steal semantics, and query inspection.
"""

import sys
import os
from typing import Dict, List, Optional, Tuple, Any, Callable, Union

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class LockInfo:
    """W3C LockInfo representation detailing a held or pending lock."""

    def __init__(self, name: str, mode: str = "exclusive", client_id: str = "client_main"):
        self.name = name
        self.mode = mode # "exclusive" or "shared"
        self.clientId = client_id

    def toJSON(self) -> Dict[str, str]:
        return {
            "name": self.name,
            "mode": self.mode,
            "clientId": self.clientId
        }

    def __repr__(self) -> str:
        return f"LockInfo({self.name}, mode={self.mode}, client={self.clientId})"


class Lock:
    """W3C Lock instance granted to callback."""

    def __init__(self, name: str, mode: str):
        self.name = name
        self.mode = mode

    def __repr__(self) -> str:
        return f"Lock({self.name}, mode={self.mode})"


class LockQueueManager:
    """Core synchronization lock manager enforcing exclusive/shared rules and FIFO queue ordering."""

    def __init__(self):
        self.held: Dict[str, List[Tuple[LockInfo, Lock]]] = {}
        self.pending: Dict[str, List[Tuple[LockInfo, Callable[[Optional[Lock]], Any]]]] = {}

    def can_acquire(self, name: str, mode: str) -> bool:
        """Determines if a lock request mode can be acquired immediately."""
        active = self.held.get(name, [])
        if not active:
            return True
        if mode == "shared" and all(info.mode == "shared" for info, _ in active):
            return True
        return False

    def request(
        self,
        name: str,
        options: Dict[str, Any],
        callback: Callable[[Optional[Lock]], Any]
    ) -> Any:
        """Processes lock request with mode ('exclusive'/'shared'), ifAvailable, and steal options."""
        mode = options.get("mode", "exclusive")
        ifAvailable = options.get("ifAvailable", False)
        steal = options.get("steal", False)
        client_id = options.get("clientId", "client_main")

        lock_info = LockInfo(name, mode, client_id)

        if steal:
            self.held[name] = []
            self.pending[name] = []

        if self.can_acquire(name, mode):
            lock = Lock(name, mode)
            self.held.setdefault(name, []).append((lock_info, lock))
            try:
                result = callback(lock)
                return result
            finally:
                self._release(name, lock)
                self._process_pending(name)
        else:
            if ifAvailable:
                return callback(None)
            else:
                self.pending.setdefault(name, []).append((lock_info, callback))
                return None

    def _release(self, name: str, lock: Lock) -> None:
        """Releases held lock instance."""
        if name in self.held:
            self.held[name] = [item for item in self.held[name] if item[1] is not lock]
            if not self.held[name]:
                del self.held[name]

    def _process_pending(self, name: str) -> None:
        """Grants pending lock requests in FIFO queue order as active locks are released."""
        while name in self.pending and self.pending[name]:
            next_info, next_cb = self.pending[name][0]
            if self.can_acquire(name, next_info.mode):
                self.pending[name].pop(0)
                if not self.pending[name]:
                    del self.pending[name]

                lock = Lock(name, next_info.mode)
                self.held.setdefault(name, []).append((next_info, lock))
                try:
                    next_cb(lock)
                finally:
                    self._release(name, lock)
            else:
                break

    def query(self) -> Dict[str, List[Dict[str, str]]]:
        """Returns snapshot listing of all held and pending locks."""
        held_list = []
        for name, items in self.held.items():
            for info, _ in items:
                held_list.append(info.toJSON())

        pending_list = []
        for name, items in self.pending.items():
            for info, _ in items:
                pending_list.append(info.toJSON())

        return {
            "held": held_list,
            "pending": pending_list
        }


class LockManager:
    """W3C LockManager navigator.locks entry point."""

    def __init__(self):
        self._manager = LockQueueManager()

    def request(
        self,
        name: str,
        options_or_callback: Union[Dict[str, Any], Callable[[Optional[Lock]], Any]],
        callback: Optional[Callable[[Optional[Lock]], Any]] = None
    ) -> Any:
        """Handles navigator.locks.request(name, options, callback) API call."""
        if callable(options_or_callback):
            cb = options_or_callback
            opts = {}
        else:
            opts = options_or_callback
            cb = callback

        if cb is None:
            raise ValueError("TypeError: A callback must be provided to navigator.locks.request().")

        return self._manager.request(name, opts, cb)

    def query(self) -> Dict[str, List[Dict[str, str]]]:
        """Handles navigator.locks.query() API call."""
        return self._manager.query()
