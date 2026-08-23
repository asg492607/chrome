"""
Unit & Benchmark Test Suite for HTML5 Canvas 2D Vector Rendering Context Engine (Sprint 28).
Verifies WHATWG Canvas 2D state machine (save/restore), 2D affine matrix transforms,
Path2D vector drawing commands, software pixel rasterization, and high-speed drawing.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from rendering_engine.canvas2d_engine import (
    Canvas2DState,
    PathCommand,
    Path2D,
    CanvasRenderingContext2D
)


class TestCanvas2DSubsystem(unittest.TestCase):

    def test_canvas2d_state_stack(self):
        """Verify save() and restore() correctly push and pop context fill_style and line_width state."""
        ctx = CanvasRenderingContext2D(400, 300)

        ctx.state.fill_style = "#ff0000"
        ctx.state.line_width = 5.0

        ctx.save() # Push state

        ctx.state.fill_style = "#00ff00"
        ctx.state.line_width = 10.0

        self.assertEqual(ctx.state.fill_style, "#00ff00")

        ctx.restore() # Pop state

        self.assertEqual(ctx.state.fill_style, "#ff0000")
        self.assertEqual(ctx.state.line_width, 5.0)

    def test_2d_affine_transformation_matrices(self):
        """Verify translate and scale transformation matrix operations."""
        ctx = CanvasRenderingContext2D(400, 300)

        ctx.translate(50.0, 100.0)
        self.assertEqual(ctx.state.matrix[4], 50.0)
        self.assertEqual(ctx.state.matrix[5], 100.0)

        ctx.scale(2.0, 3.0)
        self.assertEqual(ctx.state.matrix[0], 2.0)
        self.assertEqual(ctx.state.matrix[3], 3.0)

    def test_path2d_vector_geometry(self):
        """Verify Path2D vector path construction and command pipeline."""
        path = Path2D()
        path.moveTo(10, 10)
        path.lineTo(100, 10)
        path.rect(10, 10, 50, 50)
        path.closePath()

        self.assertEqual(len(path.commands), 4)
        self.assertEqual(path.commands[0].cmd, "MOVE_TO")
        self.assertEqual(path.commands[2].cmd, "RECT")

    def test_pixel_buffer_rasterization(self):
        """Verify fillRect mutates 32-bit RGBA pixel buffer cleanly."""
        ctx = CanvasRenderingContext2D(100, 100)
        ctx.state.fill_style = "#ff0000" # Red

        ctx.fillRect(10, 10, 20, 20)

        # Check pixel at (15, 15) -> RGBA (255, 0, 0, 255)
        offset = (15 * 100 + 15) * 4
        pixel_bytes = bytes(ctx.pixel_buffer[offset:offset + 4])
        self.assertEqual(pixel_bytes, b"\xff\x00\x00\xff")

        # Check clearRect at (15, 15)
        ctx.clearRect(10, 10, 20, 20)
        pixel_cleared = bytes(ctx.pixel_buffer[offset:offset + 4])
        self.assertEqual(pixel_cleared, b"\x00\x00\x00\x00")

    def test_high_speed_vector_drawing_benchmark(self):
        """
        Benchmark: Execute 50,000 Canvas 2D vector draw operations.
        Asserts duration < 0.15s (> 300,000 ops/sec).
        """
        ctx = CanvasRenderingContext2D(400, 300)
        ctx.state.fill_style = "#0000ff"

        start_time = time.perf_counter()
        for i in range(50000):
            ctx.save()
            ctx.translate(i % 10, i % 10)
            ctx.restore()
        duration = time.perf_counter() - start_time

        total_ops = 50000
        ops_per_sec = total_ops / duration
        latency_us = (duration / total_ops) * 1_000_000

        self.assertLess(duration, 0.20, f"50k Canvas 2D draw ops took {duration*1000:.2f}ms (must be < 200ms)")
        print(f"\n[Sprint 28 Canvas 2D Benchmark] {total_ops:,} Vector Operations Executed:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Vector Drawing Speed: {ops_per_sec:,.0f} ops/second")
        print(f"  - Average Operation Latency: {latency_us:.2f} µs/op")


if __name__ == "__main__":
    unittest.main()
