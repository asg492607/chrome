import time
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from application.events import event_bus, Events
from application.dependency_container import container

class LifecycleManager:
    """
    Coordinates the startup and shutdown sequence for the platform.
    """
    def __init__(self):
        self.is_running = False

    def start(self):
        print("[Lifecycle] Starting PacketForge Platform...")
        self.is_running = True
        event_bus.publish(Events.SYSTEM_STARTUP)
        print("[Lifecycle] System startup sequence complete.")

    def shutdown(self):
        print("[Lifecycle] Shutting down PacketForge Platform...")
        event_bus.publish(Events.SYSTEM_SHUTDOWN)
        self.is_running = False
        print("[Lifecycle] System gracefully terminated.")
