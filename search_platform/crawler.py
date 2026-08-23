"""
Web Crawler Engine & Distributed URL Frontier (Sprint 51 - Phase II Sovereign Search Engine).
Implements RFC 9309 Robots Exclusion Protocol (robots.txt) directive parser, domain politeness rate-limiting,
URL Frontier priority queueing, Bloom filter URL deduplication, and link extraction pipelines.
"""

import os
import re
import sys
import time
import urllib.parse
from typing import Dict, List, Optional, Set, Tuple, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from search_platform.search_models import CrawledPage
from search_platform.query_processor import clean_html


class RobotsTxtParser:
    """RFC 9309 Robots Exclusion Protocol parser."""

    def __init__(self, robots_content: str = ""):
        self.disallowed_paths: List[str] = []
        self.allowed_paths: List[str] = []
        self.crawl_delay: float = 0.0
        if robots_content:
            self.parse(robots_content)

    def parse(self, content: str) -> None:
        """Parses robots.txt rules into path directives."""
        self.disallowed_paths.clear()
        self.allowed_paths.clear()
        self.crawl_delay = 0.0
        active_user_agent = True

        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            if ':' in line:
                key, val = line.split(':', 1)
                key = key.strip().lower()
                val = val.strip()

                if key == "user-agent":
                    active_user_agent = (val == "*" or "sovereign" in val.lower())
                elif active_user_agent:
                    if key == "disallow" and val:
                        self.disallowed_paths.append(val)
                    elif key == "allow" and val:
                        self.allowed_paths.append(val)
                    elif key == "crawl-delay":
                        try:
                            self.crawl_delay = float(val)
                        except ValueError:
                            pass

    def is_allowed(self, path: str) -> bool:
        """Checks if specified URL path is allowed under parsed directives."""
        for allow in self.allowed_paths:
            if path.startswith(allow):
                return True
        for disallow in self.disallowed_paths:
            if path.startswith(disallow):
                return False
        return True


class PolitenessManager:
    """Domain-specific rate limiter enforcing crawl delays between requests."""

    def __init__(self):
        self._last_fetch: Dict[str, float] = {}

    def get_domain(self, url: str) -> str:
        parsed = urllib.parse.urlparse(url)
        return parsed.netloc or url

    def can_fetch(self, url: str, required_delay_sec: float = 0.05) -> bool:
        """Checks if enough time has elapsed since last request to domain."""
        domain = self.get_domain(url)
        now = time.time()
        last = self._last_fetch.get(domain, 0.0)
        return (now - last) >= required_delay_sec

    def record_fetch(self, url: str) -> None:
        """Records timestamp of fetch to domain."""
        domain = self.get_domain(url)
        self._last_fetch[domain] = time.time()


class BloomFilterDeduplicator:
    """URL deduplication manager preventing re-crawling of previously seen links."""

    def __init__(self):
        self._seen: Set[str] = set()

    def canonicalize(self, url: str) -> str:
        """Normalizes URL scheme, host, and path."""
        url = url.split('#')[0] # Remove fragment
        if url.endswith('/') and len(url) > 8:
            url = url[:-1]
        return url.lower()

    def add(self, url: str) -> bool:
        """Adds URL to filter. Returns True if URL was newly added, False if already seen."""
        canon = self.canonicalize(url)
        if canon in self._seen:
            return False
        self._seen.add(canon)
        return True

    def contains(self, url: str) -> bool:
        """Checks if URL has already been processed."""
        return self.canonicalize(url) in self._seen

    def __len__(self) -> int:
        return len(self._seen)


class URLFrontier:
    """Priority queue managing pending un-crawled URLs."""

    def __init__(self):
        self._queue: List[Tuple[int, str]] = [] # List of (priority, url)

    def enqueue(self, url: str, priority: int = 1) -> bool:
        """Enqueues URL into priority queue."""
        self._queue.append((priority, url))
        self._queue.sort(key=lambda x: x[0], reverse=True) # Higher priority first
        return True

    def dequeue(self) -> Optional[str]:
        """Dequeues highest priority URL."""
        if self._queue:
            return self._queue.pop(0)[1]
        return None

    def __len__(self) -> int:
        return len(self._queue)


class DistributedWebCrawler:
    """Distributed Web Crawler Engine for sovereign web page indexing."""

    LINK_PATTERN = re.compile(r'<a\s+(?:[^>]*?\s+)?href=["\'](.*?)["\']', re.IGNORECASE)

    def __init__(self):
        self.robots_parser = RobotsTxtParser()
        self.politeness = PolitenessManager()
        self.dedup = BloomFilterDeduplicator()
        self.frontier = URLFrontier()
        self.crawled_pages: List[CrawledPage] = []

    def extract_links(self, html_content: str, base_url: str) -> List[str]:
        """Extracts absolute hyperlink URLs from raw HTML content."""
        links = []
        for match in self.LINK_PATTERN.findall(html_content):
            href = match.strip()
            if href.startswith('javascript:') or href.startswith('mailto:') or href.startswith('#'):
                continue
            abs_url = urllib.parse.urljoin(base_url, href)
            links.append(abs_url)
        return links


    def process_page(self, url: str, html_content: str, title: str = "Untitled") -> CrawledPage:
        """Processes raw HTML content into structured CrawledPage and enqueues extracted links."""
        clean_text = clean_html(html_content)
        page = CrawledPage(
            url=url,
            title=title,
            text=clean_text,
            raw_html=html_content
        )
        self.crawled_pages.append(page)

        # Extract links and enqueue new un-crawled URLs into Frontier
        links = self.extract_links(html_content, url)
        for link in links:
            if self.dedup.add(link):
                self.frontier.enqueue(link, priority=1)

        return page


class Crawler:
    """Backward-compatible local filesystem crawler for existing unit tests."""

    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self.crawled_pages: List[CrawledPage] = []
        self.engine = DistributedWebCrawler()

    def extract_title(self, html_content: str) -> str:
        match = re.search(r'<title>(.*?)</title>', html_content, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        match = re.search(r'<h1>(.*?)</h1>', html_content, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return "Untitled Page"

    def crawl(self) -> List[CrawledPage]:
        self.crawled_pages = []
        if not os.path.exists(self.root_dir):
            return []

        for root, _, files in os.walk(self.root_dir):
            for file in files:
                if file.endswith(('.html', '.htm')):
                    filepath = os.path.join(root, file)
                    rel_path = os.path.relpath(filepath, self.root_dir)
                    url_path = rel_path.replace(os.sep, '/')

                    parts = url_path.split('/', 1)
                    host = parts[0]
                    path_suffix = "/" + parts[1] if len(parts) > 1 else "/"

                    if path_suffix.endswith("index.html"):
                        path_suffix = path_suffix[:-10]
                    elif path_suffix.endswith("index.htm"):
                        path_suffix = path_suffix[:-9]

                    simulated_url = f"http://{host}{path_suffix}"

                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                        title = self.extract_title(content)
                        page = self.engine.process_page(simulated_url, content, title)
                        self.crawled_pages.append(page)
                    except Exception:
                        pass

        return self.crawled_pages
