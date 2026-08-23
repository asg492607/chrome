"""
chromium_engine Package
==========================================================================
Clean modular exports for Chromium Runtime, WebGateway, and SearchFederator.
==========================================================================
"""

from chromium_engine.web_gateway import WebGateway
from chromium_engine.search_federator import SearchFederator
from chromium_engine.chromium_runtime import ChromiumRuntime, ChromiumTab

__all__ = [
    "WebGateway",
    "SearchFederator",
    "ChromiumRuntime",
    "ChromiumTab"
]
