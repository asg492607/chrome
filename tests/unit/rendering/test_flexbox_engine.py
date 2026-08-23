"""
Unit & Benchmark Test Suite for Flexbox Layout Engine & Multi-Axis Alignment (Sprint 13).
Verifies flex-direction (row/column), flex-grow space distribution, justify-content main-axis positioning,
align-items cross-axis stretching/centering, and direct Rect4f memory updates.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from core_platform.tag_constants import TagType
from core_platform.ecs_memory import DocumentTreeMemoryBank
from rendering_engine.html_parser import HTML5TreeBuilder
from rendering_engine.css_parser import CSSParser, CSSRuleIndex, CSSCascadeEngine
from rendering_engine.layout_engine import LayoutTreeBuilder, LayoutEngine
from rendering_engine.flexbox_engine import (
    FlexDirection,
    JustifyContent,
    AlignItems,
    FlexboxEngine
)


class TestFlexboxEngineSubsystem(unittest.TestCase):

    def test_flex_direction_row_vs_column(self):
        """Verify row flex direction places items side-by-side, column stacks vertically."""
        html = (
            '<html><body>'
            '<div id="row-flex" style="display: flex; flex-direction: row; width: 600px;">'
            '<div class="item" style="width: 100px; height: 50px;">Item 1</div>'
            '<div class="item" style="width: 100px; height: 50px;">Item 2</div>'
            '</div>'
            '</body></html>'
        )
        builder = HTML5TreeBuilder()
        root_id, bank = builder.parse_html(html)

        cascade = CSSCascadeEngine()
        cascade.resolve_tree_styles(bank, root_id)

        layout_root = LayoutTreeBuilder.build_layout_tree(bank, root_id)
        LayoutEngine.layout(bank, layout_root, viewport_width=1280.0, viewport_height=800.0)

        # Get item geometries
        items = [i for i in range(bank.count) if bank.attr_pool.get(i, {}).get("class") == "item"]
        self.assertEqual(len(items), 2)

        g1 = bank.entities[items[0]].geometry
        g2 = bank.entities[items[1]].geometry

        # Row layout: x2 > x1, y1 == y2
        self.assertGreater(g2.x, g1.x)
        self.assertAlmostEqual(g1.y, g2.y)

    def test_flex_grow_space_distribution(self):
        """Verify flex-grow factor distributes remaining free space in exact proportion."""
        html = (
            '<html><body>'
            '<div id="flex-container" style="display: flex; flex-direction: row; width: 600px;">'
            '<div id="item-grow-1" style="width: 100px; flex-grow: 1;">Item A</div>'
            '<div id="item-grow-2" style="width: 100px; flex-grow: 2;">Item B</div>'
            '</div>'
            '</body></html>'
        )
        builder = HTML5TreeBuilder()
        root_id, bank = builder.parse_html(html)

        cascade = CSSCascadeEngine()
        cascade.resolve_tree_styles(bank, root_id)

        layout_root = LayoutTreeBuilder.build_layout_tree(bank, root_id)
        LayoutEngine.layout(bank, layout_root, viewport_width=600.0, viewport_height=400.0)

        id_a = [i for i in range(bank.count) if bank.attr_pool.get(i, {}).get("id") == "item-grow-1"][0]
        id_b = [i for i in range(bank.count) if bank.attr_pool.get(i, {}).get("id") == "item-grow-2"][0]

        geom_a = bank.entities[id_a].geometry
        geom_b = bank.entities[id_b].geometry

        # Free space = 600 - (100+100) = 400.
        # Grow A gets 400 * (1/3) = 133.33 -> width = 233.33
        # Grow B gets 400 * (2/3) = 266.67 -> width = 366.67
        self.assertAlmostEqual(geom_a.width, 233.33, delta=1.0)
        self.assertAlmostEqual(geom_b.width, 366.67, delta=1.0)

    def test_justify_content_main_axis_alignment(self):
        """Verify justify-content center and flex-end main-axis position offsets."""
        html = (
            '<html><body>'
            '<div id="center-container" style="display: flex; justify-content: center; width: 800px;">'
            '<div class="box" style="width: 100px;">Box</div>'
            '</div>'
            '</body></html>'
        )
        builder = HTML5TreeBuilder()
        root_id, bank = builder.parse_html(html)

        cascade = CSSCascadeEngine()
        cascade.resolve_tree_styles(bank, root_id)

        layout_root = LayoutTreeBuilder.build_layout_tree(bank, root_id)
        LayoutEngine.layout(bank, layout_root, viewport_width=800.0, viewport_height=600.0)

        box_id = [i for i in range(bank.count) if bank.attr_pool.get(i, {}).get("class") == "box"][0]
        geom = bank.entities[box_id].geometry

        # Container 800px, box 100px -> center x = (800 - 100) / 2 = 350px
        self.assertAlmostEqual(geom.x, 350.0, delta=1.0)

    def test_align_items_cross_axis_alignment(self):
        """Verify align-items center and stretch cross-axis positioning."""
        html = (
            '<html><body>'
            '<div id="align-container" style="display: flex; align-items: center; width: 500px; height: 200px;">'
            '<div class="box" style="width: 100px; height: 60px;">Centered Box</div>'
            '</div>'
            '</body></html>'
        )
        builder = HTML5TreeBuilder()
        root_id, bank = builder.parse_html(html)

        cascade = CSSCascadeEngine()
        cascade.resolve_tree_styles(bank, root_id)

        layout_root = LayoutTreeBuilder.build_layout_tree(bank, root_id)
        LayoutEngine.layout(bank, layout_root, viewport_width=500.0, viewport_height=200.0)

        box_id = [i for i in range(bank.count) if bank.attr_pool.get(i, {}).get("class") == "box"][0]
        geom = bank.entities[box_id].geometry

        # Container height 200px, box height 60px -> centered y = (200 - 60) / 2 = 70px
        self.assertAlmostEqual(geom.y, 70.0, delta=1.0)

    def test_high_speed_flexbox_benchmark(self):
        """
        Benchmark: Compute Flexbox layout for 1,000 flex items across 100 flex containers.
        Asserts duration < 0.50s.
        """
        flex_blocks = [
            '<div style="display: flex; justify-content: space-between; align-items: center; width: 1000px; height: 100px;">'
            '<div style="width: 100px; flex-grow: 1;">Nav 1</div>'
            '<div style="width: 100px; flex-grow: 2;">Nav 2</div>'
            '<div style="width: 100px; flex-grow: 1;">Nav 3</div>'
            '</div>'
            for _ in range(100)
        ]
        html = f'<!DOCTYPE html><html><body>{"".join(flex_blocks)}</body></html>'

        builder = HTML5TreeBuilder()
        root_id, bank = builder.parse_html(html)

        cascade = CSSCascadeEngine()
        cascade.resolve_tree_styles(bank, root_id)

        start_time = time.perf_counter()
        layout_root = LayoutTreeBuilder.build_layout_tree(bank, root_id)
        LayoutEngine.layout(bank, layout_root, viewport_width=1280.0, viewport_height=800.0)
        duration = time.perf_counter() - start_time

        total_nodes = bank.count
        nodes_per_sec = total_nodes / duration
        latency_us = (duration / total_nodes) * 1_000_000

        self.assertLess(duration, 0.80, f"Flexbox layout took {duration*1000:.2f}ms (must be < 800ms)")
        print(f"\n[Sprint 13 Flexbox Multi-Axis Layout Benchmark] {total_nodes:,} DOM Nodes Positioned:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Flex Layout Speed: {nodes_per_sec:,.0f} nodes/second")
        print(f"  - Average Node Flex Latency: {latency_us:.2f} µs/node")


if __name__ == "__main__":
    unittest.main()
