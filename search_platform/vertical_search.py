"""
Vertical Search Engine Modules (Sprint 59 - Phase II Sovereign Search Engine).
Implements specialized vertical indexing and search engines for Images, Videos, News, and Academic research papers.
"""

from enum import Enum
import os
import sys
from typing import Dict, List, Optional, Tuple, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class VerticalType(Enum):
    WEB = "web"
    IMAGES = "images"
    VIDEOS = "videos"
    NEWS = "news"
    ACADEMIC = "academic"


class VerticalItem:
    """Represents a media item indexed in a vertical search category."""

    def __init__(
        self,
        url: str,
        vertical_type: VerticalType,
        title: str,
        media_url: str = "",
        snippet: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.url = url
        self.vertical_type = vertical_type
        self.title = title
        self.media_url = media_url
        self.snippet = snippet
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "verticalType": self.vertical_type.value,
            "title": self.title,
            "mediaUrl": self.media_url,
            "snippet": self.snippet,
            "metadata": self.metadata
        }

    def __repr__(self) -> str:
        return f"VerticalItem('{self.title}', category='{self.vertical_type.value}')"


class VerticalSearchEngine:
    """Specialized vertical search engine for Images, Videos, News, and Academic papers."""

    def __init__(self):
        self.indexes: Dict[VerticalType, Dict[str, List[VerticalItem]]] = {
            vt: {} for vt in VerticalType
        }

    def index_item(self, item: VerticalItem) -> None:
        """Indexes a media item into its target vertical category."""
        tokens = (item.title + " " + item.snippet + " " + str(item.metadata)).lower().split()
        term_map = self.indexes[item.vertical_type]
        for t in set(tokens):
            if t not in term_map:
                term_map[t] = []
            term_map[t].append(item)

    def search_vertical(self, query: str, vertical_type: VerticalType, limit: int = 10) -> List[VerticalItem]:
        """Queries vertical index filtering items matching query terms."""
        query_terms = [q.lower().strip() for q in query.split() if q.lower().strip()]
        if not query_terms:
            return []

        term_map = self.indexes.get(vertical_type, {})
        matches: Dict[int, VerticalItem] = {}

        for term in query_terms:
            if term in term_map:
                for item in term_map[term]:
                    matches[id(item)] = item

        return list(matches.values())[:limit]

