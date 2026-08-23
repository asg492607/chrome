"""
Unit & Benchmark Test Suite for WebGPU Sovereign Compute & Shader Execution Engine (Sprint 27).
Verifies WGSL shader parsing (@compute, @workgroup_size, @binding), GPUAdapter/GPUDevice VRAM allocation,
GPUBindGroup resource mapping, and high-speed GPUComputePipeline workgroup dispatches.
"""

import sys
import os
import unittest
import struct
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from gpu_engine.webgpu_pipeline import (
    WGSLShaderType,
    WGSLShaderModule,
    GPUBufferUsage,
    GPUBuffer,
    GPUBindGroup,
    GPUComputePipeline,
    GPUDevice,
    GPUAdapter
)


class TestWebGPUSubsystem(unittest.TestCase):

    def test_wgsl_shader_parsing(self):
        """Verify WGSLShaderModule parses @compute shader attributes, workgroup size, and resource bindings."""
        wgsl_code = """
        @compute @workgroup_size(128, 2, 1)
        fn main() {
            @group(0) @binding(0) var<storage, read_write> input_data: array<u32>;
            @group(0) @binding(1) var<uniform> params: UniformParams;
        }
        """

        module = WGSLShaderModule(wgsl_code)
        self.assertEqual(module.shader_type, WGSLShaderType.COMPUTE)
        self.assertEqual(module.workgroup_size, (128, 2, 1))
        self.assertEqual(module.bindings[0], "input_data")
        self.assertEqual(module.bindings[1], "params")

    def test_gpu_buffer_allocation_and_vram_tracking(self):
        """Verify GPUDevice allocates VRAM memory buffer and tracks total VRAM consumption."""
        adapter = GPUAdapter()
        device = adapter.request_device()

        buf = device.create_buffer(4096, GPUBufferUsage.STORAGE)
        self.assertEqual(device.vram_allocated_bytes, 4096)
        self.assertEqual(buf.size, 4096)

        test_data = struct.pack("<II", 100, 200)
        buf.write_buffer(test_data, offset=0)
        self.assertEqual(buf.read_buffer(0, 8), test_data)

    def test_compute_pipeline_workgroup_dispatch(self):
        """Verify GPUComputePipeline dispatches workgroups and updates storage buffer data in parallel."""
        adapter = GPUAdapter()
        device = adapter.request_device()

        wgsl_code = "@compute @workgroup_size(64, 1, 1)\n@group(0) @binding(0) var<storage, read_write> data: array<u32>;"
        shader = device.create_shader_module(wgsl_code)

        # Storage buffer holding 64 x u32 integers (256 bytes) initialized to 0
        buf = device.create_buffer(256, GPUBufferUsage.STORAGE)
        bind_group = device.create_bind_group({0: buf})

        pipeline = device.create_compute_pipeline(shader, bind_group)
        invocations = pipeline.dispatch_workgroups(count_x=1) # 1 workgroup * 64 threads = 64 invocations

        self.assertEqual(invocations, 64)
        # Verify first u32 element incremented from 0 to 1
        first_val = struct.unpack("<I", buf.read_buffer(0, 4))[0]
        self.assertEqual(first_val, 1)

    def test_gpu_adapter_device_request(self):
        """Verify GPUAdapter capabilities and 8 GB virtual VRAM capacity."""
        adapter = GPUAdapter(name="WebGPU Sovereign Hardware Engine")
        self.assertEqual(adapter.name, "WebGPU Sovereign Hardware Engine")
        self.assertEqual(adapter.vram_capacity_bytes, 8 * 1024 * 1024 * 1024)

    def test_high_speed_webgpu_compute_benchmark(self):
        """
        Benchmark: Dispatch 50,000 parallel WebGPU compute workgroups.
        Asserts duration < 0.20s (> 250,000 workgroups/sec).
        """
        adapter = GPUAdapter()
        device = adapter.request_device()

        shader = device.create_shader_module("@compute @workgroup_size(64, 1, 1)\n@group(0) @binding(0) var<storage> d: array<u32>;")
        buf = device.create_buffer(256, GPUBufferUsage.STORAGE)
        bind_group = device.create_bind_group({0: buf})
        pipeline = device.create_compute_pipeline(shader, bind_group)

        start_time = time.perf_counter()
        for _ in range(50000):
            _ = pipeline.dispatch_workgroups(count_x=1)
        duration = time.perf_counter() - start_time

        total_workgroups = 50000
        wg_per_sec = total_workgroups / duration
        latency_us = (duration / total_workgroups) * 1_000_000

        self.assertLess(duration, 0.20, f"50k WebGPU workgroup dispatches took {duration*1000:.2f}ms (must be < 200ms)")
        print(f"\n[Sprint 27 WebGPU Compute Benchmark] {total_workgroups:,} Workgroups Dispatched:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Workgroup Throughput: {wg_per_sec:,.0f} workgroups/second")
        print(f"  - Average Workgroup Latency: {latency_us:.2f} µs/workgroup")




if __name__ == "__main__":
    unittest.main()
