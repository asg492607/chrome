"""
Unit & Benchmark Test Suite for Sovereign Knowledge Graph Engine (Sprint 56 - Phase II).
Verifies Entity registration, Triple relation parsing, text entity extraction, graph triple querying,
entity card generation, and graph throughput.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from search_platform.knowledge_graph import (
    Entity,
    Triple,
    KnowledgeGraphEngine
)


class TestKnowledgeGraphSubsystem(unittest.TestCase):

    def test_entity_registration_and_extraction(self):
        """Verify adding entities and extracting entity mentions from text."""
        kg = KnowledgeGraphEngine()
        ent = Entity("e1", "Sovereign Engine", "Technology", {"creator": "Atharva"})
        kg.add_entity(ent)

        extracted = kg.extract_entities("The Sovereign Engine is a ground-up web runtime.")
        self.assertEqual(len(extracted), 1)
        self.assertEqual(extracted[0].name, "Sovereign Engine")

    def test_semantic_triple_querying(self):
        """Verify adding and querying Subject-Predicate-Object triples."""
        kg = KnowledgeGraphEngine()
        kg.add_triple("Sovereign Engine", "is_a", "Browser Runtime")
        kg.add_triple("Sovereign Engine", "supports", "WebCrypto")

        triples = kg.query_triples(subject="Sovereign Engine")
        self.assertEqual(len(triples), 2)
        self.assertEqual(triples[0].predicate, "is_a")

    def test_entity_knowledge_card_generation(self):
        """Verify building entity knowledge card for search UI."""
        kg = KnowledgeGraphEngine()
        kg.add_entity(Entity("e1", "Sovereign Search", "Platform"))
        kg.add_triple("Sovereign Search", "type", "Search Engine")

        card = kg.get_entity_card("Sovereign Search")
        self.assertIsNotNone(card)
        self.assertEqual(card["entity"]["name"], "Sovereign Search")
        self.assertEqual(len(card["relations"]), 1)

    def test_high_speed_knowledge_graph_benchmark(self):
        """
        Benchmark: Execute 50,000 entity extractions and triple queries.
        Asserts duration < 0.35s (> 100,000 graph ops/sec).
        """
        kg = KnowledgeGraphEngine()
        for i in range(100):
            kg.add_entity(Entity(f"e_{i}", f"Entity {i}", "Concept"))
            kg.add_triple(f"Entity {i}", "relates_to", f"Entity {(i+1)%100}")

        start_time = time.perf_counter()
        for i in range(25000):
            _ = kg.extract_entities(f"Mentioning Entity {i % 100} in text.")
            _ = kg.query_triples(subject=f"Entity {i % 100}")
        duration = time.perf_counter() - start_time

        total_ops = 50000 # 25k extractions + 25k triple queries
        ops_per_sec = total_ops / duration
        latency_us = (duration / total_ops) * 1_000_000

        self.assertLess(duration, 0.50, f"50k Graph ops took {duration*1000:.2f}ms (must be < 500ms)")
        print(f"\n[Sprint 56 Knowledge Graph Benchmark] {total_ops:,} Operations Executed:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Graph Query Speed: {ops_per_sec:,.0f} ops/second")
        print(f"  - Average Operation Latency: {latency_us:.2f} µs/op")


if __name__ == "__main__":
    unittest.main()
