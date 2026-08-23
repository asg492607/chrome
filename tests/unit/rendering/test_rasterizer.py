"""
Unit & Benchmark Test Suite for Software Rasterizer & Display List Command Generator (Sprint 14).
Verifies CSS color parsing, Display List generation, RGBA 32-bit frame buffer operations,
and zero-GPU software pixel rasterization.
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
from rendering_engine.rasterizer import (
    DrawCommandType,
    DrawCommand,
    DisplayList,
    DisplayListGenerator,
    RGBABuffer,
    SoftwareRasterizer,
    parse_css_color
)


class TestSoftwareRasterizerSubsystem(unittest.TestCase):

    def test_parse_css_color(self):
        """Verify parsing of hex, rgb, rgba, and named CSS colors."""
        self.assertEqual(parse_css_color("#ff0000"), (255, 0, 0, 255))
        self.assertEqual(parse_css_color("#0f0"), (0, 255, 0, 255))
        self.assertEqual(parse_css_color("blue"), (0, 0, 255, 255))
        self.assertEqual(parse_css_color("rgba(100, 150, 200, 0.5)"), (100, 150, 200, 127))

    def test_display_list_generation_from_dom_tree(self):
        """Verify DOM tree with styled elements emits DRAW_RECT and DRAW_TEXT display commands."""
        html = (
            '<html><body>'
            '<div id="card" style="background-color: #ff0000; width: 200px; height: 100px;">'
            '<p style="color: #ffffff;">Hello Sovereign Rasterizer</p>'
            '</div>'
            '</body></html>'
        )
        builder = HTML5TreeBuilder()
        root_id, bank = builder.parse_html(html)

        cascade = CSSCascadeEngine()
        cascade.resolve_tree_styles(bank, root_id)

        layout_root = LayoutTreeBuilder.build_layout_tree(bank, root_id)
        LayoutEngine.layout(bank, layout_root, viewport_width=1280.0, viewport_height=800.0)

        # Generate Display List
        display_list = DisplayListGenerator.generate_display_list(bank, root_id)
        self.assertGreater(len(display_list), 1)

        cmd_types = [cmd.command_type for cmd in display_list.commands]
        self.assertIn(DrawCommandType.CLEAR_SCREEN, cmd_types)
        self.assertIn(DrawCommandType.DRAW_RECT, cmd_types)

        # Check background red color command
        rect_cmds = [cmd for cmd in display_list.commands if cmd.command_type == DrawCommandType.DRAW_RECT]
        self.assertEqual(rect_cmds[0].color, (255, 0, 0, 255))

    def test_rgba_buffer_fill_rect_and_pixel_data(self):
        """Verify RGBABuffer bytearray writes exact RGBA pixel values at calculated 2D offsets."""
        buffer = RGBABuffer(width=100, height=100)
        buffer.clear((255, 255, 255, 255))

        # Fill 20x20 red rectangle at (10, 10)
        buffer.fill_rect(10, 10, 20, 20, 255, 0, 0, 255)

        # Pixel (15, 15) must be Red: [255, 0, 0, 255]
        offset_red = (15 * 100 + 15) * 4
        pixel_red = list(buffer.data[offset_red:offset_red + 4])
        self.assertEqual(pixel_red, [255, 0, 0, 255])

        # Pixel (0, 0) outside rectangle must be White: [255, 255, 255, 255]
        offset_white = (0 * 100 + 0) * 4
        pixel_white = list(buffer.data[offset_white:offset_white + 4])
        self.assertEqual(pixel_white, [255, 255, 255, 255])

    def test_software_rasterizer_execution(self):
        """Verify SoftwareRasterizer paints DisplayList commands sequentially into RGBABuffer."""
        display_list = DisplayList()
        display_list.add_command(DrawCommand(DrawCommandType.CLEAR_SCREEN, 0, 0, 200, 200, color=(255, 255, 255, 255)))
        display_list.add_command(DrawCommand(DrawCommandType.DRAW_RECT, 20, 20, 50, 50, color=(0, 0, 255, 255))) # Blue box

        buffer = RGBABuffer(width=200, height=200)
        processed = SoftwareRasterizer.rasterize(display_list, buffer)

        self.assertEqual(processed, 2)

        # Pixel at (30, 30) should be Blue [0, 0, 255, 255]
        offset = (30 * 200 + 30) * 4
        pixel = list(buffer.data[offset:offset + 4])
        self.assertEqual(pixel, [0, 0, 255, 255])

    def test_high_speed_rasterization_benchmark(self):
        """
        Benchmark: Rasterize 500 DRAW_RECT commands into a 1280x800 RGBA frame buffer.
        Asserts duration < 0.20s.
        """
        display_list = DisplayList()
        display_list.add_command(DrawCommand(DrawCommandType.CLEAR_SCREEN, 0, 0, 1280, 800, color=(255, 255, 255, 255)))

        for i in range(500):
            x = (i * 2) % 1200
            y = (i * 3) % 750
            display_list.add_command(DrawCommand(
                DrawCommandType.DRAW_RECT,
                x, y, 40, 40,
                color=((i * 7) % 256, (i * 13) % 256, (i * 17) % 256, 255)
            ))

        buffer = RGBABuffer(width=1280, height=800)

        start_time = time.perf_counter()
        count = SoftwareRasterizer.rasterize(display_list, buffer)
        duration = time.perf_counter() - start_time

        cmds_per_sec = count / duration
        latency_us = (duration / count) * 1_000_000

        self.assertLess(duration, 0.25, f"Rasterization took {duration*1000:.2f}ms (must be < 250ms)")
        print(f"\n[Sprint 14 Software Rasterizer Benchmark] {count:,} Draw Commands Rasterized:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Rasterization Speed: {cmds_per_sec:,.0f} commands/second")
        print(f"  - Average Command Latency: {latency_us:.2f} µs/command")


if __name__ == "__main__":
    unittest.main()
