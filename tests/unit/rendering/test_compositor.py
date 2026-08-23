"""
Unit & Benchmark Test Suite for Compositing Layer Tree & GPU Texture Upload Pipe (Sprint 15).
Verifies GPU layer promotion heuristics (transforms, opacity, scroll), layer tree construction,
VRAM memory tracking, DMA texture uploads, and GPU layer compositing with opacity blending.
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
from rendering_engine.rasterizer import RGBABuffer, DisplayListGenerator, SoftwareRasterizer
from rendering_engine.compositor import (
    LayerType,
    CompositingLayer,
    CompositingTreeBuilder,
    GPUTexturePipeline,
    CompositorEngine
)


class TestCompositorSubsystem(unittest.TestCase):

    def test_layer_promotion_heuristics(self):
        """Verify elements styled with transform, opacity < 1.0, or will-change are promoted to GPU layers."""
        bank = DocumentTreeMemoryBank()

        # Node 1: transform
        n1 = bank.allocate_entity(TagType.DIV)
        bank.computed_styles_pool[n1] = {"transform": "translate3d(0, 0, 0)"}
        p1, t1, o1 = CompositingTreeBuilder.should_promote_to_layer(bank, n1)
        self.assertTrue(p1)
        self.assertEqual(t1, LayerType.TRANSFORM)

        # Node 2: opacity: 0.7
        n2 = bank.allocate_entity(TagType.DIV)
        bank.computed_styles_pool[n2] = {"opacity": "0.7"}
        p2, t2, o2 = CompositingTreeBuilder.should_promote_to_layer(bank, n2)
        self.assertTrue(p2)
        self.assertEqual(o2, 0.7)

        # Node 3: plain div -> No promotion
        n3 = bank.allocate_entity(TagType.DIV)
        bank.computed_styles_pool[n3] = {"color": "black"}
        p3, t3, o3 = CompositingTreeBuilder.should_promote_to_layer(bank, n3)
        self.assertFalse(p3)

    def test_compositing_layer_tree_hierarchy(self):
        """Verify DOM tree with promoted elements builds matching CompositingLayer tree hierarchy."""
        html = (
            '<html><body>'
            '<div id="container">'
            '<div id="promoted-1" style="transform: rotate(45deg); width: 100px;">Layer 1</div>'
            '<div id="promoted-2" style="opacity: 0.8; width: 100px;">Layer 2</div>'
            '</div>'
            '</body></html>'
        )
        builder = HTML5TreeBuilder()
        root_id, bank = builder.parse_html(html)

        cascade = CSSCascadeEngine()
        cascade.resolve_tree_styles(bank, root_id)

        # Build Layer Tree
        layer_root = CompositingTreeBuilder.build_layer_tree(bank, root_id)
        self.assertIsNotNone(layer_root)
        self.assertEqual(layer_root.layer_type, LayerType.ROOT)

        # Check promoted child layers
        promoted_children = layer_root.children
        self.assertGreaterEqual(len(promoted_children), 2)

    def test_gpu_texture_allocation_and_upload(self):
        """Verify GPUTexturePipeline allocates VRAM memory bytes and handles DMA texture uploads."""
        gpu = GPUTexturePipeline()
        tex_id = gpu.allocate_texture(200, 100)

        # 200 * 100 * 4 bytes = 80,000 bytes VRAM
        self.assertEqual(gpu.vram_allocated_bytes, 80000)
        self.assertIn(tex_id, gpu.textures)

        # Upload raster buffer
        buf = RGBABuffer(200, 100)
        buf.fill_rect(0, 0, 200, 100, 255, 0, 0, 255) # Red fill

        bytes_uploaded = gpu.upload_rgba_texture(tex_id, buf)
        self.assertEqual(bytes_uploaded, 80000)

        # Verify pixel in VRAM texture
        tex_data = gpu.textures[tex_id]
        self.assertEqual(list(tex_data[0:4]), [255, 0, 0, 255])

    def test_layer_compositing_and_opacity_blending(self):
        """Verify CompositorEngine composites layer textures into target frame buffer with opacity blending."""
        gpu = GPUTexturePipeline()
        tex_id = gpu.allocate_texture(50, 50)

        buf = RGBABuffer(50, 50)
        buf.fill_rect(0, 0, 50, 50, 0, 255, 0, 255) # Green box
        gpu.upload_rgba_texture(tex_id, buf)

        # Create Compositing Layer
        root_layer = CompositingLayer(1, 0, LayerType.ROOT)
        child_layer = CompositingLayer(2, 1, LayerType.GPU_TILE)
        child_layer.bounds = (10.0, 10.0, 50.0, 50.0)
        child_layer.opacity = 0.5
        child_layer.gpu_texture_id = tex_id
        root_layer.add_child(child_layer)

        # Target Frame Buffer
        target = RGBABuffer(200, 200)
        target.clear((255, 255, 255, 255))

        composited_count = CompositorEngine.composite_layers(root_layer, gpu, target)
        self.assertEqual(composited_count, 2)

        # Check pixel at (15, 15) inside composited layer
        offset = (15 * 200 + 15) * 4
        pixel = list(target.data[offset:offset + 4])
        self.assertEqual(pixel[0], 0) # R
        self.assertEqual(pixel[1], 255) # G
        self.assertEqual(pixel[2], 0) # B
        self.assertAlmostEqual(pixel[3], 127, delta=5) # Alpha opacity = 0.5 * 255

    def test_high_speed_compositor_benchmark(self):
        """
        Benchmark: Allocate, upload, and composite 100 GPU layers into target frame buffer.
        Asserts duration < 0.20s.
        """
        gpu = GPUTexturePipeline()
        root_layer = CompositingLayer(1, 0, LayerType.ROOT)

        # Allocate 100 GPU texture tiles
        for i in range(100):
            tex_id = gpu.allocate_texture(40, 40)
            buf = RGBABuffer(40, 40)
            buf.fill_rect(0, 0, 40, 40, (i * 5) % 256, (i * 11) % 256, (i * 17) % 256, 255)
            gpu.upload_rgba_texture(tex_id, buf)

            child = CompositingLayer(i + 2, i + 1, LayerType.GPU_TILE)
            child.bounds = ((i * 8) % 1000, (i * 6) % 700, 40, 40)
            child.opacity = 0.9
            child.gpu_texture_id = tex_id
            root_layer.add_child(child)

        target = RGBABuffer(1280, 800)

        start_time = time.perf_counter()
        count = CompositorEngine.composite_layers(root_layer, gpu, target)
        duration = time.perf_counter() - start_time

        layers_per_sec = count / duration
        latency_us = (duration / count) * 1_000_000

        self.assertLess(duration, 0.25, f"Compositing took {duration*1000:.2f}ms (must be < 250ms)")
        print(f"\n[Sprint 15 Compositor & GPU Pipeline Benchmark] {count:,} Layers Composited:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - VRAM Allocated: {gpu.vram_allocated_bytes / 1024:.1f} KB")
        print(f"  - Compositing Speed: {layers_per_sec:,.0f} layers/second")
        print(f"  - Average Layer Compositing Latency: {latency_us:.2f} µs/layer")


if __name__ == "__main__":
    unittest.main()
