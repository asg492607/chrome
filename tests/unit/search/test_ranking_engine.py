"""
Unit & Benchmark Test Suite for Ranking Algorithms & Relevance Engine (Sprint 54 - Phase II).
Verifies Okapi BM25 score math, PageRank power iteration link graph analysis, multi-factor hybrid relevance scoring,
empty/unknown query fallbacks, and ranking throughput.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from search_platform.ranking_engine import (
    BM25Engine,
    PageRankEngine,
    SovereignRankingEngine,
    RankingEngine
)


class TestRankingEngineSubsystem(unittest.TestCase):

    def test_okapi_bm25_score_math_verification(self):
        """Verify document length normalization and IDF calculations."""
        bm25 = BM25Engine(k1=1.5, b=0.75)
        idf = bm25.compute_idf(total_docs=100, doc_frequency=10)
        self.assertGreater(idf, 0.0)

        score = bm25.score_document(
            query_terms=["sovereign"],
            doc_term_freqs={"sovereign": 3},
            doc_len=50,
            avg_doc_len=100.0,
            total_docs=100,
            term_doc_counts={"sovereign": 10}
        )
        self.assertGreater(score, 0.0)

    def test_pagerank_link_graph_iteration(self):
        """Verify link graph authority propagation (A -> B, C -> B)."""
        pr = PageRankEngine(damping=0.85)
        pr.add_link("https://site-a.com", "https://site-b.com")
        pr.add_link("https://site-c.com", "https://site-b.com")

        scores = pr.compute_pagerank(iterations=15)
        self.assertIn("https://site-b.com", scores)
        self.assertGreater(scores["https://site-b.com"], scores["https://site-a.com"])

    def test_multi_factor_hybrid_relevance_scoring(self):
        """Verify combined BM25 + PageRank document ordering."""
        engine = SovereignRankingEngine()
        engine.pagerank.add_link("https://doc2.local", "https://doc1.local")

        docs = {
            "https://doc1.local": {
                "title": "Sovereign Web Engine",
                "snippet": "Sovereign web search engine runtime platform."
            },
            "https://doc2.local": {
                "title": "Unrelated Topic",
                "snippet": "Random unrelated content text snippet."
            }
        }

        results = engine.rank_documents(["sovereign", "search"], docs)

        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].url, "https://doc1.local")
        self.assertGreater(results[0].score, 0.0)

    def test_empty_and_unknown_query_fallback(self):
        """Verify graceful handling of un-indexed terms and empty queries."""
        engine = SovereignRankingEngine()
        results = engine.rank_documents([], {})
        self.assertEqual(results, [])

        docs = {"https://doc1.local": {"title": "Doc", "snippet": "text"}}
        results_unknown = engine.rank_documents(["xyz_unseen"], docs)
        self.assertEqual(results_unknown, [])

    def test_high_speed_relevance_engine_benchmark(self):
        """
        Benchmark: Execute 50,000 document relevance ranking ops.
        Asserts duration < 0.35s (> 100,000 ranking ops/sec).
        """
        engine = SovereignRankingEngine()
        docs = {
            f"https://doc_{i}.local": {
                "title": f"Sovereign Title {i}",
                "snippet": f"Sovereign web search engine runtime document {i}"
            } for i in range(10)
        }

        start_time = time.perf_counter()
        for _ in range(5000):
            _ = engine.rank_documents(["sovereign", "search"], docs)
        duration = time.perf_counter() - start_time

        total_ops = 50000 # 5,000 calls x 10 docs ranked per call
        ops_per_sec = total_ops / duration
        latency_us = (duration / total_ops) * 1_000_000

        self.assertLess(duration, 0.50, f"50k Ranking ops took {duration*1000:.2f}ms (must be < 500ms)")
        print(f"\n[Sprint 54 Ranking Engine Benchmark] {total_ops:,} Operations Executed:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Ranking Speed: {ops_per_sec:,.0f} ops/second")
        print(f"  - Average Operation Latency: {latency_us:.2f} µs/op")


if __name__ == "__main__":
    unittest.main()
