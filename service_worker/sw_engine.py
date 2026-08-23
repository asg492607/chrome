"""
ServiceWorker Engine & Offline Cache Controller.
Implements WHATWG ServiceWorker lifecycle state machine (INSTALLING, ACTIVATED),
CacheStorage API, FetchEvent interception pipeline, and zero-downtime offline cache serving.
"""

import sys
import os
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class ServiceWorkerState(Enum):
    PARSED = 1
    INSTALLING = 2
    INSTALLED = 3
    ACTIVATING = 4
    ACTIVATED = 5
    REDUNDANT = 6


class CacheResponse:
    """Represents a cached HTTP response payload and headers."""
    def __init__(self, data: bytes, status: int = 200, headers: Optional[Dict[str, str]] = None):
        self.data = data
        self.status = status
        self.headers = headers if headers is not None else {"content-type": "text/html"}


class Cache:
    """WHATWG Cache object storing request-response pairs."""

    def __init__(self, name: str):
        self.name = name
        self._entries: Dict[str, CacheResponse] = {}

    def put(self, request_url: str, response_data: bytes, status: int = 200, headers: Optional[Dict[str, str]] = None) -> None:
        """Stores a request URL and response data in cache."""
        clean_url = self._normalize_url(request_url)
        self._entries[clean_url] = CacheResponse(response_data, status, headers)

    def match(self, request_url: str) -> Optional[Tuple[bytes, int, Dict[str, str]]]:
        """Matches request URL against cached entries."""
        clean_url = self._normalize_url(request_url)
        if clean_url in self._entries:
            resp = self._entries[clean_url]
            return (resp.data, resp.status, dict(resp.headers))
        return None

    def delete(self, request_url: str) -> bool:
        """Removes a request URL from cache."""
        clean_url = self._normalize_url(request_url)
        if clean_url in self._entries:
            del self._entries[clean_url]
            return True
        return False

    def keys(self) -> List[str]:
        """Returns list of cached request URLs."""
        return list(self._entries.keys())

    @classmethod
    def _normalize_url(cls, url: str) -> str:
        return url.strip().lower()


class CacheStorage:
    """WHATWG CacheStorage interface managing origin caches."""

    def __init__(self, origin: str):
        self.origin = origin
        self._caches: Dict[str, Cache] = {}

    def open(self, cache_name: str) -> Cache:
        """Opens or creates a named Cache object."""
        c_name = cache_name.strip()
        if c_name not in self._caches:
            self._caches[c_name] = Cache(c_name)
        return self._caches[c_name]

    def has(self, cache_name: str) -> bool:
        """Checks if named Cache exists."""
        return cache_name.strip() in self._caches

    def delete(self, cache_name: str) -> bool:
        """Deletes a named Cache."""
        c_name = cache_name.strip()
        if c_name in self._caches:
            del self._caches[c_name]
            return True
        return False

    def keys(self) -> List[str]:
        """Returns names of all open Cache objects."""
        return list(self._caches.keys())


class ServiceWorker:
    """WHATWG ServiceWorker instance tracking script, scope, and lifecycle state."""

    def __init__(self, script_url: str, scope: str, origin: str):
        self.script_url = script_url
        self.scope = scope.strip().lower()
        self.origin = origin.strip().lower()
        self.state = ServiceWorkerState.PARSED

    def install(self) -> None:
        """Executes ServiceWorker installation lifecycle."""
        self.state = ServiceWorkerState.INSTALLING
        # Simulate static asset pre-caching
        self.state = ServiceWorkerState.INSTALLED

    def activate(self) -> None:
        """Executes ServiceWorker activation lifecycle."""
        self.state = ServiceWorkerState.ACTIVATING
        # Simulate active claim
        self.state = ServiceWorkerState.ACTIVATED

    def is_matching_scope(self, url: str) -> bool:
        """Checks if target request URL falls within ServiceWorker scope."""
        clean_url = url.strip().lower()
        return clean_url.startswith(self.scope) or self.scope == "/"


class ServiceWorkerEngine:
    """Engine handling ServiceWorker registration and FetchEvent network interception."""

    def __init__(self):
        self._workers: Dict[Tuple[str, str], ServiceWorker] = {} # (origin, scope) -> Worker
        self._cache_storages: Dict[str, CacheStorage] = {} # origin -> CacheStorage

    def register(self, origin: str, script_url: str, scope: str = "/") -> ServiceWorker:
        """Registers, installs, and activates a ServiceWorker for target origin and scope."""
        clean_origin = origin.strip().lower()
        clean_scope = scope.strip().lower()

        worker = ServiceWorker(script_url, clean_scope, clean_origin)
        worker.install()
        worker.activate()

        self._workers[(clean_origin, clean_scope)] = worker
        if clean_origin not in self._cache_storages:
            self._cache_storages[clean_origin] = CacheStorage(clean_origin)

        return worker

    def get_cache_storage(self, origin: str) -> CacheStorage:
        """Returns origin CacheStorage instance."""
        clean_origin = origin.strip().lower()
        if clean_origin not in self._cache_storages:
            self._cache_storages[clean_origin] = CacheStorage(clean_origin)
        return self._cache_storages[clean_origin]

    def handle_fetch(
        self,
        origin: str,
        request_url: str,
        headers: Optional[Dict[str, str]] = None
    ) -> Tuple[bytes, int, Dict[str, str]]:
        """
        Intercepts outbound HTTP fetch requests.
        Checks active ServiceWorkers and CacheStorage for instant offline payload match.
        """
        clean_origin = origin.strip().lower()
        clean_url = request_url.strip().lower()

        # Check if active worker matches origin scope
        matching_worker = None
        for (w_origin, w_scope), worker in self._workers.items():
            if w_origin == clean_origin and worker.state == ServiceWorkerState.ACTIVATED:
                if worker.is_matching_scope(clean_url):
                    matching_worker = worker
                    break

        if matching_worker and clean_origin in self._cache_storages:
            cache_storage = self._cache_storages[clean_origin]
            # Search open caches for URL match
            for c_name in cache_storage.keys():
                cache = cache_storage.open(c_name)
                match_res = cache.match(clean_url)
                if match_res is not None:
                    return match_res # Return (data, status, headers) instantly!

        # Pass-through to network
        return (b"", 404, {})
