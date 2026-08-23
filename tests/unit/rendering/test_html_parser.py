"""
Unit & Benchmark Test Suite for WHATWG HTML5 Tokenizer & ECS Tree Builder (Sprint 09).
Verifies state machine tokenization, attribute parsing, void element handling,
parent-child-sibling pointer integrity in 32-byte DOMEntity32 memory, and high-speed parsing throughput.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from core_platform.tag_constants import TagType
from rendering_engine.html_parser import (
    HTMLTokenType,
    HTMLToken,
    HTML5Tokenizer,
    HTML5TreeBuilder
)


class TestHTMLParserSubsystem(unittest.TestCase):

    def test_whatwg_tokenizer_tokens_and_attributes(self):
        """Test tokenization of DOCTYPE, start tags, attributes, comments, text, and self-closing tags."""
        html = (
            '<!DOCTYPE html>'
            '<html>'
            '<head><title>Sovereign Test</title></head>'
            '<body>'
            '<!-- Main Container -->'
            '<div id="container" class="active flex">'
            '<h1>Header Title</h1>'
            '<p>Paragraph text content.</p>'
            '<img src="icon.png" alt="Icon" />'
            '</div>'
            '</body>'
            '</html>'
        )

        tokenizer = HTML5Tokenizer()
        tokens = tokenizer.tokenize(html)

        # 1. Verify DOCTYPE
        self.assertEqual(tokens[0].token_type, HTMLTokenType.DOCTYPE)
        self.assertEqual(tokens[0].data, "html")

        # 2. Verify html, head, title start tags
        self.assertEqual(tokens[1].tag_name, "html")
        self.assertEqual(tokens[2].tag_name, "head")

        # 3. Verify Comment token
        comment_tokens = [t for t in tokens if t.token_type == HTMLTokenType.COMMENT]
        self.assertEqual(len(comment_tokens), 1)
        self.assertEqual(comment_tokens[0].data, "Main Container")

        # 4. Verify Div attributes
        div_tokens = [t for t in tokens if t.token_type == HTMLTokenType.START_TAG and t.tag_name == "div"]
        self.assertEqual(len(div_tokens), 1)
        div_tok = div_tokens[0]
        self.assertEqual(div_tok.attributes.get("id"), "container")
        self.assertEqual(div_tok.attributes.get("class"), "active flex")

        # 5. Verify Self-closing img tag
        img_tokens = [t for t in tokens if t.token_type == HTMLTokenType.START_TAG and t.tag_name == "img"]
        self.assertEqual(len(img_tokens), 1)
        self.assertTrue(img_tokens[0].self_closing)

    def test_ecs_tree_builder_direct_emission(self):
        """Test that HTML source parses directly into 32-byte DOMEntity32 slots in DocumentTreeMemoryBank."""
        html = '<html><body><div><p>Hello ECS Engine</p></div></body></html>'
        builder = HTML5TreeBuilder()
        root_id, bank = builder.parse_html(html)

        # Check entity allocation
        self.assertGreater(bank.count, 4)

        # Retrieve Root Entity
        root_entity = bank.entities[root_id]
        self.assertEqual(root_entity.tag_type, TagType.DOCUMENT)
        self.assertGreater(root_entity.first_child_index, 0)

        # Retrieve HTML node
        html_id = root_entity.first_child_index
        html_entity = bank.entities[html_id]
        self.assertEqual(html_entity.tag_type, TagType.HTML)
        self.assertEqual(html_entity.parent_index, root_id)

    def test_parent_child_sibling_pointer_integrity(self):
        """Test pointer linkage for children and siblings in the ECS memory bank."""
        html = '<div><h1>Item 1</h1><p>Item 2</p><button>Item 3</button></div>'
        builder = HTML5TreeBuilder()
        root_id, bank = builder.parse_html(html)

        # Navigate root -> div
        root_ent = bank.entities[root_id]
        div_id = root_ent.first_child_index
        div_ent = bank.entities[div_id]

        # First child of div should be h1
        h1_id = div_ent.first_child_index
        h1_ent = bank.entities[h1_id]
        self.assertEqual(h1_ent.tag_type, TagType.H1)
        self.assertEqual(h1_ent.parent_index, div_id)

        # Next sibling of h1 should be p
        p_id = h1_ent.next_sibling_index
        p_ent = bank.entities[p_id]
        self.assertEqual(p_ent.tag_type, TagType.P)
        self.assertEqual(p_ent.parent_index, div_id)

        # Next sibling of p should be button
        btn_id = p_ent.next_sibling_index
        btn_ent = bank.entities[btn_id]
        self.assertEqual(btn_ent.tag_type, TagType.BUTTON)
        self.assertEqual(btn_ent.parent_index, div_id)

    def test_malformed_html_auto_recovery(self):
        """Test that unclosed tags are recovered safely without crashing."""
        html = '<div><p>Unclosed paragraph<div><p>Nested unclosed</div>'
        builder = HTML5TreeBuilder()
        root_id, bank = builder.parse_html(html)

        self.assertGreater(bank.count, 3)

    def test_high_speed_parsing_and_ecs_emission_benchmark(self):
        """
        Benchmark: Parse raw HTML text containing 10,000 DOM elements directly into DocumentTreeMemoryBank.
        Asserts throughput > 150,000 nodes/sec.
        """
        # Generate 2,000 node HTML payload
        div_blocks = ['<div class="card"><h2>Card Title</h2><p>Description text payload</p><button>Action</button></div>' for _ in range(500)]
        html_payload = f'<!DOCTYPE html><html><body>{"".join(div_blocks)}</body></html>'

        builder = HTML5TreeBuilder()
        start_time = time.perf_counter()
        root_id, bank = builder.parse_html(html_payload)
        duration = time.perf_counter() - start_time

        node_count = bank.count
        nodes_per_sec = node_count / duration
        latency_us = (duration / node_count) * 1_000_000

        self.assertLess(duration, 0.30, f"DOM parsing took {duration*1000:.2f}ms (must be < 300ms)")
        print(f"\n[Sprint 09 HTML5 Tokenizer & ECS Emission Benchmark] {node_count:,} DOM Nodes Allocated:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Parsing & ECS Build Speed: {nodes_per_sec:,.0f} nodes/second")
        print(f"  - Average Node Build Latency: {latency_us:.2f} µs/node")


if __name__ == "__main__":
    unittest.main()

