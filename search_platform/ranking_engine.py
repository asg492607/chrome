"""
Ranking Algorithms & Relevance Engine (Sprint 54 - Phase II Sovereign Search Engine).
Implements Okapi BM25 probabilistic relevance scoring (k1=1.5, b=0.75), PageRank link graph analysis (damping=0.85),
and multi-factor hybrid relevance ranking.
"""

import math
import os
import sys
from typing import Dict, List, Optional, Tuple, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from search_platform.search_models import SearchResult


class BM25Engine:
    """Okapi BM25 Probabilistic Relevance Model with document length normalization."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b

    def compute_idf(self, total_docs: int, doc_frequency: int) -> float:
        """Computes inverse document frequency using Lucene-style BM25 IDF formula."""
        if doc_frequency <= 0 or total_docs <= 0:
            return 0.0
        return math.log(((total_docs - doc_frequency + 0.5) / (doc_frequency + 0.5)) + 1.0)

    def score_document(
        self,
        query_terms: List[str],
        doc_term_freqs: Dict[str, int],
        doc_len: int,
        avg_doc_len: float,
        total_docs: int,
        term_doc_counts: Dict[str, int]
    ) -> float:
        """Calculates total Okapi BM25 relevance score for a document given query terms."""
        score = 0.0
        if avg_doc_len <= 0:
            avg_doc_len = 1.0

        for term in query_terms:
            tf = doc_term_freqs.get(term, 0)
            if tf <= 0:
                continue

            doc_cnt = term_doc_counts.get(term, 0)
            idf = self.compute_idf(total_docs, doc_cnt)

            numerator = tf * (self.k1 + 1.0)
            denominator = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / avg_doc_len))

            score += idf * (numerator / denominator)

        return score


class PageRankEngine:
    """PageRank Power Iteration Link Graph Authority Calculator."""

    def __init__(self, damping: float = 0.85):
        self.damping = damping
        self.out_links: Dict[str, List[str]] = {}
        self.in_links: Dict[str, List[str]] = {}
        self.nodes: set = set()

    def add_link(self, src: str, target: str) -> None:
        """Adds a directed hyperlink edge from src URL to target URL."""
        self.nodes.add(src)
        self.nodes.add(target)

        if src not in self.out_links:
            self.out_links[src] = []
        if target not in self.in_links:
            self.in_links[target] = []

        if target not in self.out_links[src]:
            self.out_links[src].append(target)
        if src not in self.in_links[target]:
            self.in_links[target].append(src)

    def compute_pagerank(self, iterations: int = 20) -> Dict[str, float]:
        """Calculates PageRank stationary probability scores using power iteration."""
        num_nodes = len(self.nodes)
        if num_nodes == 0:
            return {}

        initial_rank = 1.0 / num_nodes
        ranks: Dict[str, float] = {node: initial_rank for node in self.nodes}
        teleport = (1.0 - self.damping) / num_nodes

        for _ in range(iterations):
            new_ranks: Dict[str, float] = {}
            for node in self.nodes:
                incoming_score = 0.0
                inbound_nodes = self.in_links.get(node, [])
                for in_node in inbound_nodes:
                    out_count = len(self.out_links.get(in_node, []))
                    if out_count > 0:
                        incoming_score += ranks[in_node] / out_count

                new_ranks[node] = teleport + (self.damping * incoming_score)
            ranks = new_ranks

        return ranks


class SovereignRankingEngine:
    """Multi-Factor Hybrid Relevance Ranking Engine combining BM25, PageRank, and term match."""

    def __init__(self):
        self.bm25 = BM25Engine()
        self.pagerank = PageRankEngine()

    def rank_documents(
        self,
        query_terms: List[str],
        documents: Dict[str, Dict[str, Any]],
        inverted_dictionary: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """Ranks documents using hybrid BM25 term relevance and PageRank authority scores."""
        if not query_terms or not documents:
            return []

        cleaned_query = [q.lower().strip() for q in query_terms if q.lower().strip()]
        if not cleaned_query:
            return []

        total_docs = len(documents)
        doc_lens = {doc_id: doc.get("wordCount", len(doc.get("snippet", "").split())) for doc_id, doc in documents.items()}
        avg_doc_len = sum(doc_lens.values()) / max(1, total_docs)

        # Count term frequencies across documents
        doc_term_freqs: Dict[str, Dict[str, int]] = {}
        term_doc_counts: Dict[str, int] = {}

        for doc_id, doc_meta in documents.items():
            text = (doc_meta.get("title", "") + " " + doc_meta.get("snippet", "") + " " + doc_meta.get("clean_text", "")).lower()
            tokens = text.split()

            freqs: Dict[str, int] = {}
            for t in tokens:
                if t in cleaned_query:
                    freqs[t] = freqs.get(t, 0) + 1
            doc_term_freqs[doc_id] = freqs

            for t in freqs:
                term_doc_counts[t] = term_doc_counts.get(t, 0) + 1

        pr_scores = self.pagerank.compute_pagerank(iterations=10)

        # Compute hybrid relevance score per document
        scored_results: List[Tuple[float, str]] = []
        for doc_id, doc_meta in documents.items():
            bm25_score = self.bm25.score_document(
                cleaned_query,
                doc_term_freqs.get(doc_id, {}),
                doc_lens.get(doc_id, 10),
                avg_doc_len,
                total_docs,
                term_doc_counts
            )
            pr_val = pr_scores.get(doc_id, 0.0)

            # Combined score: 80% BM25 relevance + 20% PageRank link authority
            hybrid_score = (bm25_score * 0.80) + (pr_val * 20.0 * 0.20)
            if hybrid_score > 0.0001 or any(t in doc_term_freqs.get(doc_id, {}) for t in cleaned_query):
                scored_results.append((hybrid_score, doc_id))

        scored_results.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, doc_id in scored_results:
            doc_meta = documents[doc_id]
            results.append(SearchResult(
                url=doc_id,
                title=doc_meta.get("title", "Untitled"),
                snippet=doc_meta.get("snippet", ""),
                score=round(score, 4)
            ))

        return results


class RankingEngine:
    """Backward-compatible ranking interface wrapper."""

    def __init__(self):
        self.engine = SovereignRankingEngine()

    def rank(self, query_terms: List[str], inverted_index: Any, documents: Dict[str, Any]) -> List[SearchResult]:
        return self.engine.rank_documents(query_terms, documents, inverted_index)
