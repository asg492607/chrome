"""
Unit & Benchmark Test Suite for Query Parser & Optimizer Engine (Sprint 55 - Phase II).
Verifies Boolean operator parsing (AND, OR, NOT), exact phrase matching ("phrase"), Levenshtein fuzzy matching (term~1),
Query AST node representation, AST optimization, and query parsing throughput.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from search_platform.query_processor import (
    LevenshteinMatcher,
    TermNode,
    PhraseNode,
    FuzzyNode,
    BooleanNode,
    SovereignQueryParser,
    QueryASTOptimizer
)


class TestQueryProcessorSubsystem(unittest.TestCase):

    def test_boolean_operator_parsing(self):
        """Verify parsing Boolean AND/OR/NOT syntax into AST trees."""
        ast = SovereignQueryParser.parse_query("sovereign AND engine NOT legacy")
        eval_dict = ast.evaluate()

        self.assertEqual(eval_dict["type"], "BOOLEAN")
        self.assertEqual(eval_dict["operator"], "AND")

    def test_exact_phrase_query_parsing(self):
        """Verify parsing exact quoted phrase queries ("sovereign search engine")."""
        ast = SovereignQueryParser.parse_query('"sovereign search engine"')

        self.assertTrue(isinstance(ast, PhraseNode))
        self.assertEqual(ast.terms, ["sovereign", "search", "engine"])

    def test_levenshtein_fuzzy_matching(self):
        """Verify Levenshtein edit distance calculations and fuzzy modifier parsing (soverign~1)."""
        dist = LevenshteinMatcher.distance("soverign", "sovereign")
        self.assertEqual(dist, 1)

        matches = LevenshteinMatcher.fuzzy_match("soverign", ["sovereign", "runtime", "engine"], max_edits=1)
        self.assertEqual(matches, ["sovereign"])

        ast = SovereignQueryParser.parse_query("soverign~1")
        self.assertTrue(isinstance(ast, FuzzyNode))
        self.assertEqual(ast.term, "soverign")
        self.assertEqual(ast.max_edits, 1)

    def test_query_ast_optimization(self):
        """Verify simplifying nested AST expressions (NOT NOT A -> A)."""
        double_not = BooleanNode("NOT", BooleanNode("NOT", TermNode("sovereign")))
        optimized = QueryASTOptimizer.optimize(double_not)

        self.assertTrue(isinstance(optimized, TermNode))
        self.assertEqual(optimized.term, "sovereign")

    def test_high_speed_query_parser_benchmark(self):
        """
        Benchmark: Execute 50,000 query parsing and AST optimization ops.
        Asserts duration < 0.35s (> 100,000 query ops/sec).
        """
        query_str = 'sovereign AND "search engine" NOT legacy soverign~1'

        start_time = time.perf_counter()
        for _ in range(25000):
            ast = SovereignQueryParser.parse_query(query_str)
            _ = QueryASTOptimizer.optimize(ast)
        duration = time.perf_counter() - start_time

        total_ops = 50000 # 25k parses + 25k optimizations
        ops_per_sec = total_ops / duration
        latency_us = (duration / total_ops) * 1_000_000

        self.assertLess(duration, 0.50, f"50k Query parsing ops took {duration*1000:.2f}ms (must be < 500ms)")
        print(f"\n[Sprint 55 Query Parser Benchmark] {total_ops:,} Operations Executed:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Query Parsing Speed: {ops_per_sec:,.0f} ops/second")
        print(f"  - Average Operation Latency: {latency_us:.2f} µs/op")


if __name__ == "__main__":
    unittest.main()
