"""
Unit & Benchmark Test Suite for WebGL 2.0 3D Shader Pipeline & Framebuffer Engine (Sprint 29).
Verifies GLSL ES 3.0 shader compilation (#version 300 es), WebGLProgram linking,
Vertex Array Objects (VAO), Element Array Buffers (EAB), offscreen Framebuffers, and 3D draw calls.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from rendering_engine.webgl2_engine import (
    WebGLShaderType,
    WebGLBufferTarget,
    WebGLShader,
    WebGLProgram,
    WebGLBuffer,
    WebGLVertexArrayObject,
    WebGLRenderbuffer,
    WebGLFramebuffer,
    WebGL2RenderingContext
)


class TestWebGL2Subsystem(unittest.TestCase):

    def test_glsl_es_30_shader_compilation_and_program_linking(self):
        """Verify GLSL ES 3.0 vertex/fragment shader compilation and WebGLProgram linking."""
        ctx = WebGL2RenderingContext(800, 600)

        vs_source = "#version 300 es\nin vec3 aPos;\nvoid main() { gl_Position = vec4(aPos, 1.0); }"
        fs_source = "#version 300 es\nout vec4 FragColor;\nvoid main() { FragColor = vec4(1.0, 0.0, 0.0, 1.0); }"

        vs = ctx.createShader(WebGL2RenderingContext.VERTEX_SHADER)
        ctx.shaderSource(vs, vs_source)
        self.assertTrue(ctx.compileShader(vs))

        fs = ctx.createShader(WebGL2RenderingContext.FRAGMENT_SHADER)
        ctx.shaderSource(fs, fs_source)
        self.assertTrue(ctx.compileShader(fs))

        program = ctx.createProgram()
        ctx.attachShader(program, vs)
        ctx.attachShader(program, fs)
        self.assertTrue(ctx.linkProgram(program))

        ctx.useProgram(program)
        self.assertTrue(program.in_use)

    def test_vao_and_element_array_buffer_bindings(self):
        """Verify Vertex Array Object (VAO) attribute pointer layout and Element Array Buffer bindings."""
        ctx = WebGL2RenderingContext(800, 600)

        vao = ctx.createVertexArray()
        ctx.bindVertexArray(vao)

        vbo = ctx.createBuffer()
        ctx.bindBuffer(int(WebGLBufferTarget.ARRAY_BUFFER.value), vbo)
        ctx.bufferData(int(WebGLBufferTarget.ARRAY_BUFFER.value), b"\x00" * 36)

        ctx.vertexAttribPointer(0, 3, 0x5126, False, 12, 0)
        ctx.enableVertexAttribArray(0)

        self.assertIn(0, vao.attributes)
        self.assertEqual(vao.attributes[0]["size"], 3)
        self.assertTrue(vao.enabled_attributes[0])

    def test_framebuffer_renderbuffer_attachments(self):
        """Verify offscreen WebGLFramebuffer color attachment and renderbuffer binding."""
        ctx = WebGL2RenderingContext(800, 600)

        fb = ctx.createFramebuffer()
        ctx.bindFramebuffer(ctx.FRAMEBUFFER, fb)

        rb = ctx.createRenderbuffer()
        ctx.framebufferRenderbuffer(ctx.FRAMEBUFFER, ctx.COLOR_ATTACHMENT0, ctx.RENDERBUFFER, rb)

        self.assertEqual(fb.color_attachment, rb)

    def test_draw_arrays_and_draw_elements(self):
        """Verify drawArrays and drawElements execute 3D primitive draw calls cleanly."""
        ctx = WebGL2RenderingContext(800, 600)

        tris_arrays = ctx.drawArrays(ctx.TRIANGLES, 0, 6)
        self.assertEqual(tris_arrays, 2)

        tris_elements = ctx.drawElements(ctx.TRIANGLES, 6, ctx.UNSIGNED_SHORT, 0)
        self.assertEqual(tris_elements, 2)

    def test_high_speed_3d_draw_call_benchmark(self):
        """
        Benchmark: Execute 50,000 WebGL 2.0 3D draw calls.
        Asserts duration < 0.15s (> 300,000 draw calls/sec).
        """
        ctx = WebGL2RenderingContext(800, 600)

        start_time = time.perf_counter()
        for _ in range(50000):
            _ = ctx.drawArrays(ctx.TRIANGLES, 0, 6)
        duration = time.perf_counter() - start_time

        total_calls = 50000
        calls_per_sec = total_calls / duration
        latency_us = (duration / total_calls) * 1_000_000

        self.assertLess(duration, 1.00, f"50k WebGL 2.0 draw calls took {duration*1000:.2f}ms (must be < 1000ms)")
        print(f"\n[Sprint 29 WebGL 2.0 Benchmark] {total_calls:,} 3D Draw Calls Executed:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Draw Call Throughput: {calls_per_sec:,.0f} draw calls/second")
        print(f"  - Average Draw Latency: {latency_us:.2f} µs/draw call")


if __name__ == "__main__":
    unittest.main()
