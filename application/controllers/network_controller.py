import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from networking_stack.dhcp_server import DHCPServer, run_dhcp_client
from networking_stack.dns_server import DNSServer
from networking_stack.reverse_proxy import ReverseProxy
from networking_stack.mock_web_server import MockWebServer
from application.events import event_bus, Events

class NetworkController:
    """
    Public interface for controlling the Networking Stack.
    """
    def __init__(self):
        self.dhcp = DHCPServer()
        self.dns = DNSServer()
        self.proxy = ReverseProxy()
        self.mock_web = MockWebServer(port=8081)
        
    def initialize(self):
        event_bus.subscribe(Events.SYSTEM_STARTUP, self.start_all)
        event_bus.subscribe(Events.SYSTEM_SHUTDOWN, self.stop_all)

    def start_all(self):
        self.dhcp.start()
        self.dns.start()
        self.proxy.start()
        self.mock_web.start()
        event_bus.publish(Events.PROXY_CONNECTED)

    def stop_all(self):
        self.mock_web.stop()
        self.proxy.stop()
        self.dns.stop()
        self.dhcp.stop()

    def resolve_dns(self, hostname):
        return self.dns.resolve(hostname)
        
    def configure_dhcp(self):
        config = run_dhcp_client(server_port=6767)
        if config:
            event_bus.publish(Events.DHCP_ASSIGNED, config)
        return config
