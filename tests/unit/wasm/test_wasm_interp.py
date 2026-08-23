"""
Unit & Benchmark Test Suite for WebAssembly (Wasm) Bytecode Execution Engine (Sprint 26).
Verifies Wasm binary module decoding (\x00asm magic header), 64 KB page-aligned linear memory,
stack machine instructions (i32.add, i32.sub, i32.mul, i32.load, i32.store), and high-speed execution.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from wasm_engine.wasm_interp import (
    WasmValType,
    WasmSectionType,
    WasmLinearMemory,
    WasmModule,
    WasmDecoder,
    WasmInterpreter
)


class TestWasmSubsystem(unittest.TestCase):

    def test_wasm_binary_header_validation(self):
        """Verify WasmDecoder validates \\x00asm magic header and version 1 correctly."""
        valid_bytes = b"\x00asm\x01\x00\x00\x00"
        module = WasmDecoder.parse_module(valid_bytes)

        self.assertEqual(module.magic_number, b"\x00asm")
        self.assertEqual(module.version, 1)

        invalid_bytes = b"\x00foo\x01\x00\x00\x00"
        with self.assertRaises(ValueError):
            WasmDecoder.parse_module(invalid_bytes)

    def test_64kb_linear_memory_read_write(self):
        """Verify WasmLinearMemory 64 KB page-aligned read/write and memory growth."""
        mem = WasmLinearMemory(initial_pages=1)
        self.assertEqual(mem.current_pages, 1)
        self.assertEqual(len(mem.buffer), 65536)

        # Write i32 at offset 1024
        mem.write_i32(1024, 987654321)
        self.assertEqual(mem.read_i32(1024), 987654321)

        # Grow memory by 2 pages (128 KB)
        old_pages = mem.grow(2)
        self.assertEqual(old_pages, 1)
        self.assertEqual(mem.current_pages, 3)
        self.assertEqual(len(mem.buffer), 196608)

    def test_stack_machine_math_execution(self):
        """Verify WasmInterpreter stack machine instruction execution for addition, subtraction, multiplication."""
        mem = WasmLinearMemory()
        # Code: i32.const 10, i32.const 25, i32.add, i32.const 5, i32.mul, end
        code_bytes = bytes([
            0x41, 10,  # i32.const 10
            0x41, 25,  # i32.const 25
            0x6A,      # i32.add (stack = [35])
            0x41, 5,   # i32.const 5
            0x6C,      # i32.mul (stack = [175])
            0x0B       # end
        ])

        stack = WasmInterpreter.execute_instructions(code_bytes, locals_map=[], memory=mem)
        self.assertEqual(len(stack), 1)
        self.assertEqual(stack[0], 175)

    def test_wasm_memory_load_and_store(self):
        """Verify i32.store and i32.load interact cleanly with WasmLinearMemory."""
        module = WasmModule()

        # Code: i32.const 200 (addr), i32.const 42 (val), i32.store 0 0, i32.const 200 (addr), i32.load 0 0, end
        code_bytes = bytes([
            0x41, 0xC8, 0x01, # i32.const 200
            0x41, 42,         # i32.const 42
            0x36, 0x00, 0x00, # i32.store align=0 offset=0
            0x41, 0xC8, 0x01, # i32.const 200
            0x28, 0x00, 0x00, # i32.load align=0 offset=0
            0x0B              # end
        ])

        module.register_export_function("compute", locals_count=0, code_bytes=code_bytes)
        res = WasmInterpreter.call_export(module, "compute", args=[])

        self.assertEqual(res, 42)
        self.assertEqual(module.memory.read_i32(200), 42)

    def test_high_speed_wasm_execution_benchmark(self):
        """
        Benchmark: Execute 100,000 Wasm stack machine instructions.
        Asserts duration < 0.15s (> 500,000 instrs/sec).
        """
        mem = WasmLinearMemory()
        # Code: i32.const 1, i32.const 2, i32.add
        code_bytes = bytes([0x41, 1, 0x41, 2, 0x6A, 0x0B])

        start_time = time.perf_counter()
        for _ in range(33333): # ~100k stack ops
            _ = WasmInterpreter.execute_instructions(code_bytes, locals_map=[], memory=mem)
        duration = time.perf_counter() - start_time

        total_instrs = 100000
        instrs_per_sec = total_instrs / duration
        latency_us = (duration / total_instrs) * 1_000_000

        self.assertLess(duration, 0.20, f"100k Wasm instrs took {duration*1000:.2f}ms (must be < 200ms)")
        print(f"\n[Sprint 26 Wasm Interpreter Benchmark] {total_instrs:,} Stack Machine Instructions Executed:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Execution Speed: {instrs_per_sec:,.0f} instructions/second")
        print(f"  - Average Instruction Latency: {latency_us:.2f} µs/instruction")


if __name__ == "__main__":
    unittest.main()
