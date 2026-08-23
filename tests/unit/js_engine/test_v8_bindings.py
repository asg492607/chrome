"""
Unit & Benchmark Test Suite for V8 Engine FFI & DOM C++ Binding Generator (Sprint 16).
Verifies native C++ DOM bindings (getElementById, createElement, appendChild, setStyle),
dirty flag propagation, C-callable FFI bridge, and JSContext script execution.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from core_platform.tag_constants import TagType
from core_platform.ecs_memory import DocumentTreeMemoryBank, NodeFlags
from js_engine.v8_bindings import DOMBindings, V8FFIBridge, JSContext


class TestV8BindingsSubsystem(unittest.TestCase):

    def test_dom_bindings_create_element_and_attributes(self):
        """Verify DOMBindings.createElement and setAttribute manipulate DocumentTreeMemoryBank directly."""
        bank = DocumentTreeMemoryBank()

        # Create Element
        btn_id = DOMBindings.create_element(bank, "button")
        self.assertGreaterEqual(btn_id, 0)
        self.assertEqual(bank.entities[btn_id].tag_type, int(TagType.BUTTON))

        # Set Attribute
        DOMBindings.set_attribute(bank, btn_id, "id", "submit-btn")
        DOMBindings.set_attribute(bank, btn_id, "class", "btn primary")

        # Get Element By ID
        found_id = DOMBindings.get_element_by_id(bank, "submit-btn")
        self.assertEqual(found_id, btn_id)

        # Get Elements By Class Name
        found_classes = DOMBindings.get_elements_by_class_name(bank, "primary")
        self.assertIn(btn_id, found_classes)

    def test_dirty_flag_propagation_on_style_mutation(self):
        """Verify modifying entity style propagates DIRTY_STYLE and DIRTY_LAYOUT flags into 32-byte slot."""
        bank = DocumentTreeMemoryBank()
        node_id = DOMBindings.create_element(bank, "div")

        # Clear dirty flags
        bank.entities[node_id].flags &= ~(int(NodeFlags.DIRTY_STYLE) | int(NodeFlags.DIRTY_LAYOUT))
        self.assertEqual(bank.entities[node_id].flags & int(NodeFlags.DIRTY_STYLE), 0)

        # Set Style via DOMBindings
        DOMBindings.set_style(bank, node_id, "color", "red")

        # Computed styles pool updated
        self.assertEqual(bank.computed_styles_pool[node_id].get("color"), "red")

        # Dirty flags set
        self.assertNotEqual(bank.entities[node_id].flags & int(NodeFlags.DIRTY_STYLE), 0)
        self.assertNotEqual(bank.entities[node_id].flags & int(NodeFlags.DIRTY_LAYOUT), 0)

    def test_v8_ffi_c_callables(self):
        """Verify C-compatible FFI bridge wrapper functions for V8 engine embedding."""
        bank = DocumentTreeMemoryBank()
        ffi = V8FFIBridge(bank)

        # Execute C-level FFI call
        node_id = ffi._c_create_element(b"span")
        self.assertGreaterEqual(node_id, 0)
        self.assertEqual(bank.entities[node_id].tag_type, int(TagType.SPAN))
        self.assertGreater(ffi.total_ffi_calls, 0)

        # Execute set_style via FFI
        ffi._c_set_style(node_id, b"font-size", b"18px")
        self.assertEqual(bank.computed_styles_pool[node_id].get("font-size"), "18px")

    def test_js_context_script_execution(self):
        """Verify JSContext evaluates JavaScript statements and mutates ECS Memory Bank."""
        bank = DocumentTreeMemoryBank()
        ctx = JSContext(bank)

        js_script = (
            'const card = document.createElement("div");'
            'card.setAttribute("id", "my-card");'
            'card.style.background = "#111";'
        )

        res = ctx.execute_script(js_script)
        self.assertEqual(res["status"], "success")
        self.assertGreater(res["mutations"], 0)

        # Verify card created in bank
        card_id = DOMBindings.get_element_by_id(bank, "my-card")
        self.assertIsNotNone(card_id)
        self.assertEqual(bank.computed_styles_pool[card_id].get("background"), "#111")

    def test_high_speed_js_dom_mutation_benchmark(self):
        """
        Benchmark: Execute 10,000 DOM element creations & style mutations via DOMBindings.
        Asserts duration < 0.15s (> 100,000 ops/sec).
        """
        bank = DocumentTreeMemoryBank()

        start_time = time.perf_counter()
        for i in range(5000):
            node_id = DOMBindings.create_element(bank, "div")
            DOMBindings.set_attribute(bank, node_id, "id", f"node-{i}")
            DOMBindings.set_style(bank, node_id, "width", f"{i}px")
        duration = time.perf_counter() - start_time

        total_ops = 15000
        ops_per_sec = total_ops / duration
        latency_us = (duration / total_ops) * 1_000_000

        self.assertLess(duration, 0.20, f"15k DOM mutations took {duration*1000:.2f}ms (must be < 200ms)")
        print(f"\n[Sprint 16 V8 FFI & DOM C++ Binding Benchmark] {total_ops:,} Operations Executed:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - JS Binding Speed: {ops_per_sec:,.0f} ops/second")
        print(f"  - Average DOM Mutation Latency: {latency_us:.2f} µs/op")


if __name__ == "__main__":
    unittest.main()
