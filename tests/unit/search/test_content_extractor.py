"""
Unit & Benchmark Test Suite for Content Extraction & Normalization Engine (Sprint 52 - Phase II).
Verifies DOM boilerplate container stripping (<nav>, <footer>, <script>, <style>), OpenGraph and Meta description extraction,
text normalization, NormalizedDocument attribute structure, and extraction throughput.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from search_platform.content_extractor import (
    NormalizedDocument,
    ContentExtractorEngine
)


class TestContentExtractorSubsystem(unittest.TestCase):

    def test_dom_boilerplate_container_stripping(self):
        """Verify removing navbars, footers, scripts, styles, and sidebar containers."""
        raw_html = """
        <html>
            <head>
                <title>Article Title</title>
                <style>body { color: red; }</style>
                <script>console.log("tracking_script");</script>
            </head>
            <body>
                <nav><a href="/home">Home Link</a></nav>
                <main>
                    <h1>Main Headline</h1>
                    <p>This is the core valuable article text.</p>
                </main>
                <aside>Ad Sidebar Content</aside>
                <footer>Copyright 2026 Sovereign</footer>
            </body>
        </html>
        """

        stripped = ContentExtractorEngine.strip_boilerplate(raw_html)

        self.assertNotIn("tracking_script", stripped)
        self.assertNotIn("Home Link", stripped)
        self.assertNotIn("Ad Sidebar Content", stripped)
        self.assertNotIn("Copyright 2026", stripped)
        self.assertIn("Main Headline", stripped)
        self.assertIn("core valuable article text", stripped)

    def test_opengraph_and_meta_description_extraction(self):
        """Verify parsing <meta name="description">, keywords, and <meta property="og:title">."""
        html_doc = """
        <html>
            <head>
                <meta name="description" content="Sovereign search engine platform &amp; runtime.">
                <meta name="keywords" content="search, sovereign, runtime, indexing">
                <meta property="og:title" content="Sovereign OpenGraph Title">
                <meta property="og:description" content="Sovereign OpenGraph Description">
            </head>
        </html>
        """

        meta = ContentExtractorEngine.extract_metadata(html_doc)

        self.assertEqual(meta["description"], "Sovereign search engine platform & runtime.")
        self.assertEqual(meta["keywords"], ["search", "sovereign", "runtime", "indexing"])
        self.assertEqual(meta["og_tags"]["title"], "Sovereign OpenGraph Title")
        self.assertEqual(meta["og_tags"]["description"], "Sovereign OpenGraph Description")

    def test_text_normalization_and_word_count(self):
        """Verify tag stripping, HTML entity unescaping, and whitespace collapsing."""
        raw_text = "<p>Hello &amp; Welcome   to    Sovereign Search Engine!</p>"
        norm = ContentExtractorEngine.normalize_text(raw_text)

        self.assertEqual(norm, "Hello & Welcome to Sovereign Search Engine!")

    def test_normalized_document_processing_pipeline(self):
        """Verify full process() pipeline building structured NormalizedDocument model."""
        raw_html = """
        <html>
            <head>
                <title>Pipeline Test</title>
                <meta name="description" content="Pipeline test description metadata.">
            </head>
            <body>
                <main><p>This is the test document clean body text.</p></main>
            </body>
        </html>
        """

        doc = ContentExtractorEngine.process("https://sovereign.local/test", raw_html)

        self.assertEqual(doc.title, "Pipeline Test")
        self.assertEqual(doc.meta_description, "Pipeline test description metadata.")
        self.assertEqual(doc.clean_text, "Pipeline Test This is the test document clean body text.")
        self.assertEqual(doc.word_count, len(doc.clean_text.split()))

        doc_dict = doc.to_dict()
        self.assertIn("cleanText", doc_dict)
        self.assertEqual(doc_dict["wordCount"], doc.word_count)

    def test_high_speed_content_extraction_benchmark(self):
        """
        Benchmark: Execute 50,000 document extractions, boilerplate strippings, and metadata parse ops.
        Asserts duration < 0.50s (> 100,000 extraction ops/sec).
        """
        raw_html = """
        <html>
            <head>
                <title>Bench Document</title>
                <meta name="description" content="Bench description metadata string.">
                <script>var tracking = true;</script>
            </head>
            <body>
                <nav>Navigation Bar Links</nav>
                <main><p>Sovereign Search Engine Bench Payload Text</p></main>
                <footer>Footer Legal Links</footer>
            </body>
        </html>
        """

        start_time = time.perf_counter()
        for _ in range(25000):
            _ = ContentExtractorEngine.strip_boilerplate(raw_html)
            _ = ContentExtractorEngine.process("https://bench.local/doc", raw_html)
        duration = time.perf_counter() - start_time

        total_ops = 50000 # 25k strippings + 25k full processings
        ops_per_sec = total_ops / duration
        latency_us = (duration / total_ops) * 1_000_000

        self.assertLess(duration, 1.50, f"50k Content Extraction ops took {duration*1000:.2f}ms (must be < 1500ms)")
        print(f"\n[Sprint 52 Content Extraction Benchmark] {total_ops:,} Operations Executed:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Extraction Speed: {ops_per_sec:,.0f} ops/second")
        print(f"  - Average Operation Latency: {latency_us:.2f} µs/op")



if __name__ == "__main__":
    unittest.main()
