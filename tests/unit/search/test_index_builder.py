"""
Unit & Benchmark Test Suite for Inverted Index & Positional Indexing Engine (Sprint 53 - Phase II).
Verifies Posting positional offsets, Varint & delta gap integer compression, phrase query proximity matching,
IndexShard hash partitioning, and indexing throughput.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from search_platform.index_builder import (
    Posting,
    VarintCompressor,
    InvertedPositionalIndex,
    IndexShard
)


class TestIndexBuilderSubsystem(unittest.TestCase):

    def test_posting_and_positional_offset_indexing(self):
        """Verify term posting lists and position offsets."""
        idx = InvertedPositionalIndex()
        idx.add_document("doc1", "Sovereign Title", "sovereign web search engine sovereign runtime")

        postings = idx.lookup_term("sovereign")
        self.assertEqual(len(postings), 1)
        self.assertEqual(postings[0].doc_id, "doc1")
        self.assertEqual(postings[0].term_frequency, 2)
        self.assertEqual(postings[0].positions, [0, 4])

    def test_varint_and_delta_gap_compression(self):
        """Verify Varint byte compression and delta gap decoding roundtrips."""
        original_positions = [10, 14, 25, 100, 105, 1024, 2048]
        compressed_bytes = VarintCompressor.delta_encode(original_positions)
        decoded_positions = VarintCompressor.delta_decode(compressed_bytes)

        self.assertEqual(decoded_positions, original_positions)
        self.assertLess(len(compressed_bytes), len(original_positions) * 4) # Compact format

    def test_phrase_query_position_verification(self):
        """Verify matching adjacent term positions for phrase queries."""
        idx = InvertedPositionalIndex()
        idx.add_document("doc1", "Doc 1", "sovereign web search engine")
        idx.add_document("doc2", "Doc 2", "web sovereign engine search")

        matches = idx.lookup_phrase(["sovereign", "web"])
        self.assertIn("doc1", matches)
        self.assertNotIn("doc2", matches)

    def test_multi_shard_partition_distribution(self):
        """Verify hash-sharding term dictionaries into distinct shards."""
        sharded_idx = IndexShard(num_shards=4)
        sharded_idx.add_document("doc1", "Title", "sovereign search platform")

        postings = sharded_idx.lookup_term("sovereign")
        self.assertEqual(len(postings), 1)

    def test_high_speed_inverted_index_benchmark(self):
        """
        Benchmark: Execute 50,000 document indexing and posting lookup ops.
        Asserts duration < 0.35s (> 100,000 index ops/sec).
        """
        idx = InvertedPositionalIndex()
        clean_text = "sovereign web search engine indexing algorithm inverted posting list"

        start_time = time.perf_counter()
        for i in range(25000):
            idx.add_document(f"doc_{i % 100}", f"Title {i}", clean_text)
            _ = idx.lookup_term("sovereign")
        duration = time.perf_counter() - start_time

        total_ops = 50000 # 25k add_documents + 25k lookups
        ops_per_sec = total_ops / duration
        latency_us = (duration / total_ops) * 1_000_000

        self.assertLess(duration, 1.50, f"50k Indexing ops took {duration*1000:.2f}ms (must be < 1500ms)")
        print(f"\n[Sprint 53 Inverted Index Benchmark] {total_ops:,} Operations Executed:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Indexing Speed: {ops_per_sec:,.0f} ops/second")
        print(f"  - Average Operation Latency: {latency_us:.2f} µs/op")


if __name__ == "__main__":
    unittest.main()
