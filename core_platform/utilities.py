"""
Shared utilities across the PacketForge platform.
"""

def sanitize_url(url: str) -> str:
    """Basic utility to clean URLs."""
    return url.strip().lower()
