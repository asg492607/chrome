"""
chromium_engine/search_federator.py
==========================================================================
Dual-Tier Search Federator: Internal Sovereign Priority + Live External Web

Executes high-relevance searches with 2-tier ranking:
1. Tier 1 (Top Priority): Local Sovereign Inverted Index, Knowledge Graph,
   Internal Blog Posts, Tech News Articles, and Engine Architecture.
2. Tier 2 (Secondary): Real-time live external web queries via Wikipedia
   Search API and HackerNews / Web APIs.
==========================================================================
"""

import json
import os
import urllib.request
import urllib.parse
import ssl
import threading
from typing import List, Dict, Any
from core_platform.logging_system import sys_logger
from search_platform.index_builder import IndexBuilder
from search_platform.query_processor import process_query
from search_platform.ranking_engine import RankingEngine
from search_platform.search_config import SearchConfig


class SearchFederator:
    """Federates queries across internal sovereign databases and external live web."""

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

        # Load internal inverted index
        index_file = os.path.join(self.base_dir, 'search_index.json')
        self.indexer = IndexBuilder(index_file)
        self.indexer.load_index()
        self.ranking_engine = RankingEngine()

        # Curated internal sovereign index
        self.internal_docs = [
            {
                "url": "/blog/",
                "title": "The Packet Hacker — Low-Level Networking & Systems Blog",
                "snippet": "Exploring low-level networking, DHCP DORA handshake, DNS resolution caching, TCP socket streaming, and raw packet crafting.",
                "source": "sovereign",
                "badge": "🛡️ Sovereign Internal",
                "score": 0.995,
                "tags": ["blog", "packet", "networking", "dhcp", "dns", "python", "systems"]
            },
            {
                "url": "/news/",
                "title": "Global Tech News — Artificial Intelligence & Engineering Trends",
                "snippet": "Breaking engineering trends and software releases. Special reports on Agentic Coding teams, Gemini AI models, and browser architecture advancements.",
                "source": "sovereign",
                "badge": "🛡️ Sovereign Internal",
                "score": 0.990,
                "tags": ["news", "tech", "ai", "agents", "gemini", "trends", "articles"]
            },
            {
                "url": "/about",
                "title": "Sovereign Search Platform — Phase II Complete (Sprints 51–60)",
                "snippet": "A complete information retrieval engine: RFC 9309 crawler, varint positional inverted index, Okapi BM25 + PageRank ranking, and Knowledge Graph entity extraction.",
                "source": "sovereign",
                "badge": "🛡️ Sovereign Internal",
                "score": 0.985,
                "tags": ["search", "engine", "phase2", "phase 2", "bm25", "pagerank", "crawler", "sovereign"]
            },
            {
                "url": "/about",
                "title": "Sovereign Browser Engine — Phase I Complete (50 Sprints)",
                "snippet": "A ground-up web browser runtime engineered across 50 sprints. Covers HTTP/3, TLS 1.3, Layout ECS, WebGPU, and W3C Web APIs without Chromium or WebKit dependencies.",
                "source": "sovereign",
                "badge": "🛡️ Sovereign Internal",
                "score": 0.980,
                "tags": ["browser", "engine", "sovereign", "runtime", "chromium", "webkit", "http3", "tls"]
            },
            {
                "url": "/settings",
                "title": "Chromium & ASG Engine Settings",
                "source": "sovereign",
                "badge": "🛡️ Sovereign Internal",
                "snippet": "Configure cache policies, network proxying, zero-tracking privacy parameters, and font rendering engines.",
                "score": 0.920,
                "tags": ["settings", "config", "privacy", "cache", "chromium"]
            },
            {
                "url": "/history",
                "title": "Session Navigation History",
                "source": "sovereign",
                "badge": "🛡️ Sovereign Internal",
                "snippet": "Inspect sovereign browsing session history, active leases, and visited URLs.",
                "score": 0.910,
                "tags": ["history", "session", "logs", "urls"]
            }
        ]

    def search(self, query: str) -> Dict[str, Any]:
        """
        Runs federated search:
        - Tier 1: Internal Sovereign Results (Prioritized at Top)
        - Tier 2: Live External Internet Web Results
        """
        query = query.strip()
        if not query:
            return {"query": "", "total": 0, "results": []}

        internal_results = []
        external_results = []

        # 1. Search Internal Databases (Tier 1 Priority)
        q_lower = query.lower()
        terms = [t for t in q_lower.split() if t]

        for doc in self.internal_docs:
            score = doc["score"]
            matched = False
            title_l = doc["title"].lower()
            snippet_l = doc["snippet"].lower()
            tags = [t.lower() for t in doc.get("tags", [])]

            for term in terms:
                if term in title_l:
                    score += 0.25
                    matched = True
                elif any(term in tag for tag in tags):
                    score += 0.20
                    matched = True
                elif term in snippet_l:
                    score += 0.10
                    matched = True

            if matched:
                item = dict(doc)
                item["score"] = round(score, 4)
                internal_results.append(item)

        # Index builder search
        try:
            self.indexer.load_index()
            query_terms = process_query(query, SearchConfig.STOP_WORDS)
            ranked_raw = self.ranking_engine.rank(query_terms, self.indexer.index, self.indexer.documents)
            for item in ranked_raw:
                # Add if not already present
                if not any(r["url"] == item.url for r in internal_results):
                    internal_results.append({
                        "url": item.url,
                        "title": item.title,
                        "snippet": item.snippet,
                        "source": "sovereign",
                        "badge": "🛡️ Sovereign Internal",
                        "score": round(item.score + 0.5, 4)  # Priority boost for internal
                    })
        except Exception as e:
            sys_logger.log(f"[SearchFederator] Internal index error: {e}")

        # Sort internal results descending by score
        internal_results.sort(key=lambda x: x["score"], reverse=True)

        # 2. Concurrently fetch Live External Web Results (Tier 2)
        ext_thread = threading.Thread(target=self._fetch_external_web, args=(query, external_results))
        ext_thread.start()
        ext_thread.join(timeout=2.0)  # Maximum 2 seconds timeout for external queries

        # Combine with Tier 1 First, Tier 2 Second
        all_results = internal_results + external_results

        return {
            "query": query,
            "internal_count": len(internal_results),
            "external_count": len(external_results),
            "total": len(all_results),
            "results": all_results
        }

    def _fetch_external_web(self, query: str, out_list: List[Dict[str, Any]]):
        """Fetches live search results from Wikipedia OpenSearch API and live web."""
        try:
            encoded_q = urllib.parse.quote(query)
            api_url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={encoded_q}&limit=6&namespace=0&format=json"
            
            req = urllib.request.Request(
                api_url,
                headers={'User-Agent': 'ASGWorldChromium/2.0 (Mozilla/5.0)'}
            )
            with urllib.request.urlopen(req, context=self.ssl_context, timeout=1.8) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if len(data) >= 4:
                    titles = data[1]
                    descriptions = data[2]
                    urls = data[3]
                    
                    for i in range(len(titles)):
                        t = titles[i]
                        d = descriptions[i] or f"Live article for {t} on Wikipedia encyclopedia."
                        u = urls[i]
                        out_list.append({
                            "url": f"/proxy?url={urllib.parse.quote(u)}",
                            "direct_url": u,
                            "title": f"{t} — Wikipedia",
                            "snippet": d,
                            "source": "live_web",
                            "badge": "🌐 Live Web",
                            "score": round(0.75 - (i * 0.05), 4)
                        })
        except Exception as e:
            sys_logger.log(f"[SearchFederator] External search warning: {e}")
