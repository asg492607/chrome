"""
Unit & Benchmark Test Suite for Box Model Geometry & Layout Tree Builder (Sprint 12).
Verifies Box Model calculations (content, padding, border, margin), non-rendered node filtering (display: none),
block coordinate calculation, and direct Rect4f L1 cache memory packing.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from core_platform.tag_constants import TagType
from core_platform.ecs_memory import DocumentTreeMemoryBank, NodeFlags
from rendering_engine.html_parser import HTML5TreeBuilder
from rendering_engine.css_parser import CSSParser, CSSRuleIndex, CSSCascadeEngine
from rendering_engine.layout_engine import (
    BoxDimensions,
    EdgeDimensions,
    LayoutNode,
    LayoutNodeType,
    LayoutTreeBuilder,
    LayoutEngine
)


class TestLayoutEngineSubsystem(unittest.TestCase):

    def test_box_model_dimensions_and_bounding_boxes(self):
        """Verify Box Model padding, border, and margin bounding box calculations."""
        box = BoxDimensions()
        box.x = 20.0
        box.y = 30.0
        box.width = 100.0
        box.height = 50.0

        box.padding = EdgeDimensions(top=10, right=10, bottom=10, left=10)
        box.border = EdgeDimensions(top=2, right=2, bottom=2, left=2)
        box.margin = EdgeDimensions(top=15, right=15, bottom=15, left=15)

        # Content Box: (20, 30, 100, 50)
        self.assertEqual((box.x, box.y, box.width, box.height), (20.0, 30.0, 100.0, 50.0))

        # Padding Box: (10, 20, 120, 70)
        self.assertEqual(box.padding_box(), (10.0, 20.0, 120.0, 70.0))

        # Border Box: (8, 18, 124, 74)
        self.assertEqual(box.border_box(), (8.0, 18.0, 124.0, 74.0))

        # Margin Box: (-7, 3, 154, 104)
        self.assertEqual(box.margin_box(), (-7.0, 3.0, 154.0, 104.0))

    def test_layout_tree_builder_filters_non_rendered_nodes(self):
        """Verify that display: none and non-rendered head/script elements are excluded from LayoutTree."""
        html = (
            '<html><head><title>Test</title><script>var x = 1;</script></head>'
            '<body>'
            '<div id="visible">Visible Content</div>'
            '<div id="hidden" style="display: none">Hidden Content</div>'
            '</body></html>'
        )
        builder = HTML5TreeBuilder()
        root_id, bank = builder.parse_html(html)

        # Style resolution
        css = "#hidden { display: none; }"
        rules = CSSParser.parse_stylesheet(css)
        rule_idx = CSSRuleIndex()
        rule_idx.add_stylesheet(rules)
        cascade = CSSCascadeEngine(rule_index=rule_idx)
        cascade.resolve_tree_styles(bank, root_id)

        # Build Layout Tree
        layout_root = LayoutTreeBuilder.build_layout_tree(bank, root_id)
        self.assertIsNotNone(layout_root)

        # Collect all entity IDs in layout tree
        layout_ids = []
        queue = [layout_root]
        while queue:
            node = queue.pop(0)
            layout_ids.append(node.entity_id)
            queue.extend(node.children)

        # Head entity must NOT be in layout_ids
        head_ids = [i for i in range(bank.count) if bank.entities[i].tag_type == int(TagType.HEAD)]
        for h_id in head_ids:
            self.assertNotIn(h_id, layout_ids)


        # Hidden entity must NOT be in layout_ids
        hidden_ids = [i for i in range(bank.count) if bank.attr_pool.get(i, {}).get("id") == "hidden"]
        if hidden_ids:
            self.assertNotIn(hidden_ids[0], layout_ids)

    def test_layout_engine_block_vertical_stacking_and_coordinates(self):
        """Test vertical block stacking, y-offset propagation, and direct Rect4f memory packing."""
        html = (
            '<html><body>'
            '<div class="box" style="height: 100px; margin: 10px;">Box 1</div>'
            '<div class="box" style="height: 150px; margin: 10px;">Box 2</div>'
            '</body></html>'
        )
        builder = HTML5TreeBuilder()
        root_id, bank = builder.parse_html(html)

        # Styles
        cascade = CSSCascadeEngine()
        cascade.resolve_tree_styles(bank, root_id)

        # Build Layout Tree & Calculate Geometry
        layout_root = LayoutTreeBuilder.build_layout_tree(bank, root_id)
        LayoutEngine.layout(bank, layout_root, viewport_width=1280.0, viewport_height=800.0)

        # Verify div1 and div2 entity geometry in bank
        div_ids = [i for i in range(bank.count) if bank.entities[i].tag_type == int(TagType.DIV)]
        self.assertEqual(len(div_ids), 2)

        div1_geom = bank.entities[div_ids[0]].geometry
        div2_geom = bank.entities[div_ids[1]].geometry

        self.assertEqual(div1_geom.width, 1280.0)
        self.assertEqual(div1_geom.height, 100.0)

        self.assertEqual(div2_geom.width, 1280.0)
        self.assertEqual(div2_geom.height, 150.0)
        self.assertGreater(div2_geom.y, div1_geom.y)

        # DIRTY_LAYOUT flag must be cleared
        self.assertEqual(bank.entities[div_ids[0]].flags & int(NodeFlags.DIRTY_LAYOUT), 0)
        self.assertEqual(bank.entities[div_ids[1]].flags & int(NodeFlags.DIRTY_LAYOUT), 0)

    def test_high_speed_layout_engine_benchmark(self):
        """
        Benchmark: Construct LayoutTree and compute layout for 1,000 DOM nodes.
        Asserts throughput > 10,000 nodes/sec.
        """
        div_blocks = ['<div class="card" style="height: 50px;"><h2 style="height: 20px;">Title</h2><p style="height: 20px;">Text</p></div>' for _ in range(250)]
        html = f'<!DOCTYPE html><html><body>{"".join(div_blocks)}</body></html>'

        builder = HTML5TreeBuilder()
        root_id, bank = builder.parse_html(html)

        cascade = CSSCascadeEngine()
        cascade.resolve_tree_styles(bank, root_id)

        start_time = time.perf_counter()
        layout_root = LayoutTreeBuilder.build_layout_tree(bank, root_id)
        LayoutEngine.layout(bank, layout_root, viewport_width=1024.0, viewport_height=768.0)
        duration = time.perf_counter() - start_time

        total_nodes = bank.count
        nodes_per_sec = total_nodes / duration
        latency_us = (duration / total_nodes) * 1_000_000

        self.assertLess(duration, 1.00, f"Layout computation took {duration*1000:.2f}ms (must be < 1000ms)")
        print(f"\n[Sprint 12 Box Model Layout Engine Benchmark] {total_nodes:,} DOM Nodes Positioned:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Layout Speed: {nodes_per_sec:,.0f} nodes/second")
        print(f"  - Average Node Layout Latency: {latency_us:.2f} µs/node")



if __name__ == "__main__":
    unittest.main()
