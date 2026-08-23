import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from browser_engine.browser import Browser
from application.events import event_bus, Events

class BrowserController:
    """
    Public interface for controlling the Browser Engine.
    """
    def __init__(self):
        self.browser_app = None

    def initialize(self):
        # We don't start the Tkinter loop here because it blocks.
        # We instantiate it and provide a way to boot it.
        self.browser_app = Browser()
        
        # Subscribe to events
        event_bus.subscribe(Events.DHCP_ASSIGNED, self._on_dhcp_assigned)
        event_bus.subscribe(Events.DHCP_RELEASED, self._on_dhcp_released)
        
    def open_url(self, url):
        if self.browser_app:
            self.browser_app.navigate(url)
            event_bus.publish(Events.PAGE_LOADED, url)

    def reload(self):
        if self.browser_app:
            self.browser_app.refresh()

    def render(self, html):
        if self.browser_app:
            self.browser_app.render_pipeline(html)
            event_bus.publish(Events.PAGE_RENDERED)

    def close(self):
        if self.browser_app and self.browser_app.window:
            self.browser_app.window.destroy()

    def start_ui(self):
        if self.browser_app:
            self.browser_app.run()

    # Event Handlers
    def _on_dhcp_assigned(self, config):
        if self.browser_app:
            self.browser_app.dhcp_config = config
            self.browser_app.window.lbl_ip.config(text=f"IP Address: {config['ip']}", fg="#34d399")
            self.browser_app.window.lbl_gateway.config(text=f"Gateway IP: {config['router']}", fg="#cbd5e1")
            self.browser_app.window.lbl_dns.config(text=f"DNS Server: {config['dns']}", fg="#cbd5e1")

    def _on_dhcp_released(self):
        if self.browser_app:
            self.browser_app.release_dhcp()
