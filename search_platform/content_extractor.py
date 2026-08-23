"""
Content Extraction & Normalization Engine (Sprint 52 - Phase II Sovereign Search Engine).
Implements HTML boilerplate container stripping (<script>, <style>, <nav>, <footer>, <header>),
meta description and OpenGraph tag extraction, text normalization, and NormalizedDocument modeling.
"""

import os
import re
import sys
import html
from typing import Dict, List, Optional, Tuple, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class NormalizedDocument:
    """Structured noise-free document representation ready for search engine indexing."""

    def __init__(
        self,
        url: str,
        title: str,
        clean_text: str,
        meta_description: str = "",
        og_tags: Optional[Dict[str, str]] = None,
        keywords: Optional[List[str]] = None,
        word_count: int = 0,
        language: str = "en"
    ):
        self.url = url
        self.title = title
        self.clean_text = clean_text
        self.meta_description = meta_description
        self.og_tags = og_tags or {}
        self.keywords = keywords or []
        self.word_count = word_count
        self.language = language

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "cleanText": self.clean_text,
            "metaDescription": self.meta_description,
            "ogTags": self.og_tags,
            "keywords": self.keywords,
            "wordCount": self.word_count,
            "language": self.language
        }

    def __repr__(self) -> str:
        return f"NormalizedDocument('{self.title}', words={self.word_count}, url='{self.url}')"


class ContentExtractorEngine:
    """Engine parsing raw HTML into clean NormalizedDocument models."""

    BOILERPLATE_PATTERN = re.compile(
        r'<(?:script|style|nav|footer|header|aside|iframe)\b.*?>.*?</(?:script|style|nav|footer|header|aside|iframe)>',
        re.DOTALL | re.IGNORECASE
    )
    BOILERPLATE_PATTERNS = [BOILERPLATE_PATTERN]

    META_DESC_PATTERN = re.compile(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', re.IGNORECASE)
    META_KEYS_PATTERN = re.compile(r'<meta\s+name=["\']keywords["\']\s+content=["\'](.*?)["\']', re.IGNORECASE)
    OG_TAG_PATTERN = re.compile(r'<meta\s+property=["\']og:(.*?)["\']\s+content=["\'](.*?)["\']', re.IGNORECASE)
    TITLE_PATTERN = re.compile(r'<title>(.*?)</title>', re.IGNORECASE)
    TAG_STRIP_PATTERN = re.compile(r'<.*?>', re.DOTALL)
    WHITESPACE_PATTERN = re.compile(r'\s+')

    @classmethod
    def strip_boilerplate(cls, raw_html: str) -> str:
        """Removes script, style, nav, footer, header, and sidebar containers."""
        return cls.BOILERPLATE_PATTERN.sub(' ', raw_html)

    @classmethod
    def extract_metadata(cls, raw_html: str) -> Dict[str, Any]:
        """Extracts meta description, keywords, and OpenGraph metadata tags."""
        description = ""
        keywords = []
        og_tags = {}

        desc_match = cls.META_DESC_PATTERN.search(raw_html)
        if desc_match:
            description = html.unescape(desc_match.group(1).strip())

        keys_match = cls.META_KEYS_PATTERN.search(raw_html)
        if keys_match:
            raw_keys = keys_match.group(1)
            keywords = [k.strip().lower() for k in raw_keys.split(',') if k.strip()]

        for og_prop, og_val in cls.OG_TAG_PATTERN.findall(raw_html):
            og_tags[og_prop.strip().lower()] = html.unescape(og_val.strip())

        return {
            "description": description,
            "keywords": keywords,
            "og_tags": og_tags
        }

    @classmethod
    def normalize_text(cls, html_str: str) -> str:
        """Strips tags, unescapes entities, and collapses whitespace."""
        text_only = cls.TAG_STRIP_PATTERN.sub(' ', html_str)
        unescaped = html.unescape(text_only)
        collapsed = cls.WHITESPACE_PATTERN.sub(' ', unescaped).strip()
        return collapsed

    @classmethod
    def extract_title(cls, raw_html: str) -> str:
        """Extracts title from <title> tag or default fallback."""
        match = cls.TITLE_PATTERN.search(raw_html)
        if match:
            return html.unescape(match.group(1).strip())
        return "Untitled Document"

    @classmethod
    def process(cls, url: str, raw_html: str, title: Optional[str] = None) -> NormalizedDocument:
        """Processes raw HTML into a clean NormalizedDocument ready for search indexing."""
        metadata = cls.extract_metadata(raw_html)
        doc_title = title or metadata["og_tags"].get("title") or cls.extract_title(raw_html)

        stripped_html = cls.strip_boilerplate(raw_html)
        clean_text = cls.normalize_text(stripped_html)

        words = clean_text.split()
        word_count = len(words)

        desc = metadata["description"] or metadata["og_tags"].get("description", "")
        if not desc and len(clean_text) > 0:
            desc = clean_text[:160] + "..." if len(clean_text) > 160 else clean_text

        return NormalizedDocument(
            url=url,
            title=doc_title,
            clean_text=clean_text,
            meta_description=desc,
            og_tags=metadata["og_tags"],
            keywords=metadata["keywords"],
            word_count=word_count,
            language="en"
        )
