import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from search_platform.search_api import SearchAPI
from search_platform.crawler import Crawler
from search_platform.index_builder import IndexBuilder
from application.events import event_bus, Events

class SearchController:
    """
    Public interface for controlling the Search Platform.
    """
    def __init__(self):
        self.search_api = SearchAPI(port=8082)
        
    def initialize(self):
        event_bus.subscribe(Events.SYSTEM_STARTUP, self.start_service)
        event_bus.subscribe(Events.SYSTEM_SHUTDOWN, self.stop_service)

    def start_service(self):
        self.search_api.start()

    def stop_service(self):
        self.search_api.stop()

    def index_site(self, root_dir):
        crawler = Crawler(root_dir)
        pages = crawler.crawl()
        
        builder = IndexBuilder()
        builder.build_index(pages)
        event_bus.publish(Events.INDEX_UPDATED, len(pages))
        
        # Reload api index
        self.search_api.index_builder.load_index()

    def rebuild_index(self):
        # Default mock paths
        self.index_site(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../mock_web')))
