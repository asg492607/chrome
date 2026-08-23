class Configuration:
    """Centralized configuration for PacketForge."""
    def __init__(self):
        self.DHCP_PORT = 67
        self.DNS_PORT = 53
        self.HTTP_PORT = 80
        self.DASHBOARD_PORT = 8282

config = Configuration()
