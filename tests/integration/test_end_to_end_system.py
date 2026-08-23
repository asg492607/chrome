"""
End-to-End System & Sovereign Search Integration Test Suite.
Verifies complete end-to-end integration across all 4 phases:
- Phase I: Sovereign Browser Engine Foundations (DOM, Cascade, Layout, asg:// protocol)
- Phase II: Sovereign Search Platform (Crawler, Extractor, Inverted Index, BM25/PageRank, Query AST, Knowledge Graph, Autocomplete, Privacy, Verticals)
- Phase III: Chromium-Backed Modular Runtime (WebGateway, SearchFederator, Session/Tab Management)
- Phase IV: Sovereign Application UI & Gateway Integration (asgsearch.local, Reverse Proxy, Virtual Hosts)
"""

import os
import sys
import unittest
import urllib.parse

# Setup root path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from search_platform.search_master import SovereignSearchPlatformMaster
from search_platform.crawler import Crawler
from search_platform.index_builder import IndexBuilder
from search_platform.query_processor import process_query, tokenize
from search_platform.ranking_engine import RankingEngine
from search_platform.knowledge_graph import Entity
from search_platform.search_config import SearchConfig
from chromium_engine.search_federator import SearchFederator
from chromium_engine.chromium_runtime import ChromiumRuntime
from chromium_engine.web_gateway import WebGateway
from browser_engine.asg_protocol_handler import AsgProtocolHandler
from browser_engine.parsing.dom_builder import DOMBuilder
from browser_engine.styling.cascade_engine import CascadeEngine
from browser_engine.layout.layout_engine import LayoutEngine
from networking_stack.reverse_proxy import ReverseProxyEngine
from networking_stack.adblock_engine import adblock_engine


class TestEndToEndSystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        cls.mock_web_dir = os.path.join(cls.base_dir, 'mock_web')

    def test_search_platform_end_to_end_pipeline(self):
        """Verify the full 10-subsystem Sovereign Search Platform end-to-end pipeline."""
        master = SovereignSearchPlatformMaster()

        # 1. Index mock corpus documents
        doc1_html = """
        <html>
            <head>
                <title>Distributed Systems Architecture</title>
                <meta name="description" content="Deep dive into distributed systems, consensus algorithms, and networking protocols.">
                <script>console.log('telemetry');</script>
            </head>
            <body>
                <nav><a href="/">Home</a></nav>
                <main>
                    <h1>Distributed Systems</h1>
                    <p>Understanding Raft consensus, Byzantine fault tolerance, and low latency socket communication.</p>
                </main>
                <footer>Copyright 2026</footer>
            </body>
        </html>
        """
        doc1 = master.index_document("https://systems.local/dist", doc1_html, "Distributed Systems Architecture")
        self.assertIsNotNone(doc1)
        self.assertEqual(doc1.title, "Distributed Systems Architecture")
        self.assertIn("Raft consensus", doc1.clean_text)

        # 2. Add Knowledge Graph entity
        master.kg.add_entity(Entity("e_dist", "Distributed Systems", "Technology", {"topic": "Computer Science"}))
        master.kg.add_triple("Distributed Systems", "relies_on", "Consensus Algorithms")

        # 3. Execute full end-to-end search
        res = master.execute_end_to_end_search("consensus")
        self.assertEqual(res["status"], 200)
        self.assertGreaterEqual(res["totalResults"], 1)
        self.assertEqual(res["results"][0]["url"], "https://systems.local/dist")
        self.assertTrue(res["privacyProtected"])
        self.assertIsNotNone(res["entityCard"])
        self.assertIn("Distributed Systems", res["entityCard"]["entity"]["name"])

        # 4. Verify Autocomplete
        suggestions = master.autocomplete.autocomplete("dist", limit=5)
        self.assertTrue(any("dist" in s.lower() for s in suggestions))

    def test_mock_web_crawling_and_indexing(self):
        """Verify crawling mock_web directory, computing TF-IDF/BM25, and searching."""
        crawler = Crawler(self.mock_web_dir)
        pages = crawler.crawl()
        self.assertGreater(len(pages), 0, "Should find HTML pages in mock_web directory")

        builder = IndexBuilder()
        builder.build_index(pages)
        self.assertGreater(len(builder.documents), 0)

        # Test ranking
        ranker = RankingEngine()
        query_terms = process_query("python", SearchConfig.STOP_WORDS)
        results = ranker.rank(query_terms, builder.index, builder.documents)
        self.assertIsInstance(results, list)

    def test_chromium_runtime_and_federator(self):
        """Verify Chromium runtime session management and Search Federator."""
        runtime = ChromiumRuntime()
        tab1 = runtime.create_tab("asg://world", "ASG World")
        self.assertEqual(runtime.active_tab_id, tab1.tab_id)
        self.assertEqual(len(runtime.tabs), 1)

        tab1.navigate("asg://about", "About ASG")
        self.assertEqual(tab1.url, "asg://about")
        self.assertEqual(len(tab1.history), 2)

        # Search Federator
        federator = SearchFederator(self.base_dir)
        search_res = federator.search("networking")
        self.assertIn("query", search_res)
        self.assertIn("results", search_res)
        self.assertGreater(len(search_res["results"]), 0)

    def test_browser_engine_asg_protocol_and_layout(self):
        """Verify asg:// protocol resolution, DOM building, style cascading, and layout generation."""
        handler = AsgProtocolHandler(self.base_dir)
        self.assertTrue(handler.is_asg_url("asg://about"))

        html_content, logs = handler.resolve("asg://about")
        self.assertIn("<html", html_content.lower())
        self.assertGreater(len(logs), 0)

        # Layout pipeline
        dom = DOMBuilder().build(html_content)
        CascadeEngine().apply_styles(dom)
        boxes = LayoutEngine(canvas_width=800).compute_layout(dom)
        self.assertGreater(len(boxes), 0, "Layout engine should generate layout boxes for asg://about")

    def test_reverse_proxy_and_adblock_security(self):
        """Verify Reverse Proxy route configuration, adblocking layer-1 drop, and egress sandbox."""
        proxy = ReverseProxyEngine(host="127.0.0.1", port=8999)
        self.assertIn("asgsearch.local", proxy.routes)
        self.assertIn("myblog.com", proxy.routes)

        # Adblock Engine Layer-1 check
        is_blocked, rule = adblock_engine.should_block("adservice.google.com", "/ads/banner.js")
        self.assertTrue(is_blocked)

        # Egress Sandbox check
        allowed, reason = proxy.egress_sandbox.is_egress_allowed("telemetry.google.com")
        self.assertFalse(allowed)


if __name__ == "__main__":
    unittest.main()
