import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from application.dependency_container import container
from application.lifecycle import LifecycleManager
from application.controllers.browser_controller import BrowserController
from application.controllers.network_controller import NetworkController
from application.controllers.search_controller import SearchController
from application.controllers.dashboard_controller import DashboardController

class PlatformController:
    """
    The Brain. Coordinates subsystems, startup sequences, and component registration.
    """
    def __init__(self):
        self.lifecycle = LifecycleManager()

    def initialize_components(self):
        print("[Platform] Initializing components...")
        
        # Instantiate controllers
        browser_ctrl = BrowserController()
        network_ctrl = NetworkController()
        search_ctrl = SearchController()
        dashboard_ctrl = DashboardController()

        # Register in Dependency Container
        container.register("BrowserController", browser_ctrl)
        container.register("NetworkController", network_ctrl)
        container.register("SearchController", search_ctrl)
        container.register("DashboardController", dashboard_ctrl)
        container.register("LifecycleManager", self.lifecycle)

        # Call their initialization logic (subscribing to events, etc.)
        browser_ctrl.initialize()
        network_ctrl.initialize()
        search_ctrl.initialize()
        dashboard_ctrl.initialize()

        print("[Platform] Component registration complete.")

    def boot(self):
        # Fire SYSTEM_STARTUP (starts servers)
        self.lifecycle.start()
        
        # Crawl and index immediately so search works on boot
        search_ctrl = container.resolve("SearchController")
        print("[Platform] Pre-building search index...")
        search_ctrl.rebuild_index()

    def launch_uis(self):
        """
        In a real application, multiple Tkinter roots in different threads is tricky.
        For demonstration, we might just start one, or run them in separate processes.
        Here we'll boot the browser. The dashboard could be run standalone.
        """
        print("[Platform] Launching UIs...")
        
        # Getting controllers
        browser_ctrl = container.resolve("BrowserController")
        dashboard_ctrl = container.resolve("DashboardController")
        
        # We start the browser UI. 
        # Note: Tkinter requires the mainloop to be on the main thread.
        # We can't easily run both windows on the same thread without a shared root.
        # We'll prioritize the Browser UI for this entry point.
        browser_ctrl.start_ui()

    def shutdown(self):
        self.lifecycle.shutdown()
