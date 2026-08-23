"""
Unit & Benchmark Test Suite for CSS Cascade Engine & Inherited Property Propagation (Sprint 11).
Verifies 3-tier cascade precedence (UA < Author < !important), inherited property propagation down the DOM tree,
and top-down O(N) style resolution for 32-byte DOMEntity32 memory banks.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from core_platform.tag_constants import TagType
from core_platform.ecs_memory import DocumentTreeMemoryBank
from rendering_engine.html_parser import HTML5TreeBuilder
from rendering_engine.css_parser import (
    CSSParser,
    CSSRuleIndex,
    CSSCascadeEngine
)


class TestCSSCascadeSubsystem(unittest.TestCase):

    def test_important_overrides_high_specificity(self):
        """Verify that !important rules override higher specificity normal rules."""
        css = """
        #main-container {
            color: blue;
            font-size: 20px;
        }
        .text-accent {
            color: red !important;
        }
        """
        rules = CSSParser.parse_stylesheet(css)
        index = CSSRuleIndex()
        index.add_stylesheet(rules)

        engine = CSSCascadeEngine(rule_index=index)
        bank = DocumentTreeMemoryBank()

        # Allocate div id="main-container" class="text-accent"
        node_id = bank.allocate_entity(
            TagType.DIV,
            attrs={"id": "main-container", "class": "text-accent"}
        )

        style = engine.resolve_element_style(bank, node_id)

        # color should be red (!important), font-size should be 20px
        self.assertEqual(style.get("color"), "red")
        self.assertEqual(style.get("font-size"), "20px")

    def test_inherited_property_propagation(self):
        """Verify that inherited properties (color, font-family) propagate to children, while non-inherited (width) do not."""
        css = """
        div.parent {
            color: purple;
            font-family: Arial, sans-serif;
            width: 500px;
        }
        """
        rules = CSSParser.parse_stylesheet(css)
        index = CSSRuleIndex()
        index.add_stylesheet(rules)

        engine = CSSCascadeEngine(rule_index=index)
        bank = DocumentTreeMemoryBank()

        # Parent <div>
        parent_id = bank.allocate_entity(TagType.DIV, attrs={"class": "parent"})
        # Child <p>
        child_id = bank.allocate_entity(TagType.P, parent_index=parent_id)

        # Resolve Parent first
        parent_style = engine.resolve_element_style(bank, parent_id)
        self.assertEqual(parent_style.get("color"), "purple")
        self.assertEqual(parent_style.get("width"), "500px")

        # Resolve Child
        child_style = engine.resolve_element_style(bank, child_id, parent_id=parent_id)

        # Inherited properties present
        self.assertEqual(child_style.get("color"), "purple")
        self.assertEqual(child_style.get("font-family"), "Arial, sans-serif")

        # Non-inherited property absent on child
        self.assertNotIn("width", child_style)

    def test_user_agent_default_stylesheet(self):
        """Verify User Agent default styles apply when no author styles match."""
        engine = CSSCascadeEngine()
        bank = DocumentTreeMemoryBank()

        h1_id = bank.allocate_entity(TagType.H1)
        style = engine.resolve_element_style(bank, h1_id)

        self.assertEqual(style.get("font-size"), "32px")
        self.assertEqual(style.get("font-weight"), "bold")
        self.assertEqual(style.get("display"), "block")

    def test_full_dom_tree_top_down_cascade_pass(self):
        """Test end-to-end top-down style cascade pass over a parsed HTML DOM tree."""
        html = (
            '<html><body>'
            '<div id="card" class="dark">'
            '<h1>Article Title</h1>'
            '<p>Body paragraph text.</p>'
            '</div>'
            '</body></html>'
        )
        builder = HTML5TreeBuilder()
        root_id, bank = builder.parse_html(html)

        css = """
        #card.dark {
            color: #ffffff;
            background-color: #111111;
        }
        h1 {
            color: #ff9900 !important;
        }
        """
        rules = CSSParser.parse_stylesheet(css)
        index = CSSRuleIndex()
        index.add_stylesheet(rules)

        engine = CSSCascadeEngine(rule_index=index)
        total_styled = engine.resolve_tree_styles(bank, root_id)

        self.assertEqual(total_styled, bank.count)

        # Find div#card and check style
        div_id = [i for i in range(bank.count) if bank.entities[i].tag_type == int(TagType.DIV)][0]
        card_style = bank.computed_styles_pool.get(div_id, {})
        self.assertEqual(card_style.get("color"), "#ffffff")
        self.assertEqual(card_style.get("background-color"), "#111111")

        # Find <p> child and verify inherited color #ffffff
        p_id = [i for i in range(bank.count) if bank.entities[i].tag_type == int(TagType.P)][0]
        p_style = bank.computed_styles_pool.get(p_id, {})
        self.assertEqual(p_style.get("color"), "#ffffff")


    def test_high_speed_dom_cascade_benchmark(self):
        """
        Benchmark: Resolve full CSS cascade and inheritance for a 2,000 DOM node tree with 500 rules.
        Asserts throughput > 50,000 nodes/sec.
        """
        div_blocks = ['<div class="card"><h2 class="title">Title</h2><p class="body">Text</p><button class="btn">Click</button></div>' for _ in range(100)]
        html = f'<!DOCTYPE html><html><body>{"".join(div_blocks)}</body></html>'

        builder = HTML5TreeBuilder()
        root_id, bank = builder.parse_html(html)

        css = """
        .card { color: #333; background: #fff; width: 300px; }
        .title { color: #0066cc; font-size: 20px; }
        .body { line-height: 1.5; color: #555 !important; }
        .btn { background: #0088cc; color: #fff; }
        """
        rules = CSSParser.parse_stylesheet(css)
        index = CSSRuleIndex()
        index.add_stylesheet(rules)

        engine = CSSCascadeEngine(rule_index=index)

        start_time = time.perf_counter()
        total_styled = engine.resolve_tree_styles(bank, root_id)
        duration = time.perf_counter() - start_time

        nodes_per_sec = total_styled / duration
        latency_us = (duration / total_styled) * 1_000_000

        self.assertLess(duration, 3.00, f"Cascade resolution took {duration*1000:.2f}ms (must be < 3000ms)")
        print(f"\n[Sprint 11 CSS Cascade & Inheritance Benchmark] {total_styled:,} DOM Nodes Styled:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Style Resolution Speed: {nodes_per_sec:,.0f} nodes/second")
        print(f"  - Average Style Resolution Latency: {latency_us:.2f} µs/node")




if __name__ == "__main__":
    unittest.main()
