from collections import defaultdict
import threading

class EventBus:
    """
    A simple thread-safe synchronous event dispatcher to decouple subsystems.
    """
    def __init__(self):
        self._listeners = defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, event_type, callback):
        with self._lock:
            if callback not in self._listeners[event_type]:
                self._listeners[event_type].append(callback)

    def unsubscribe(self, event_type, callback):
        with self._lock:
            if callback in self._listeners[event_type]:
                self._listeners[event_type].remove(callback)

    def publish(self, event_type, *args, **kwargs):
        with self._lock:
            callbacks = list(self._listeners.get(event_type, []))
            
        for callback in callbacks:
            try:
                callback(*args, **kwargs)
            except Exception as e:
                print(f"[EventBus] Error dispatching '{event_type}' to {callback}: {e}")

# Global singleton event bus
event_bus = EventBus()

# Well-known event types
class Events:
    SYSTEM_STARTUP = "SYSTEM_STARTUP"
    SYSTEM_SHUTDOWN = "SYSTEM_SHUTDOWN"
    
    DNS_RESOLVED = "DNS_RESOLVED"
    HTTP_REQUEST_SENT = "HTTP_REQUEST_SENT"
    PAGE_LOADED = "PAGE_LOADED"
    PAGE_RENDERED = "PAGE_RENDERED"
    
    SEARCH_COMPLETED = "SEARCH_COMPLETED"
    INDEX_UPDATED = "INDEX_UPDATED"
    
    PROXY_CONNECTED = "PROXY_CONNECTED"
    DHCP_ASSIGNED = "DHCP_ASSIGNED"
    DHCP_RELEASED = "DHCP_RELEASED"
