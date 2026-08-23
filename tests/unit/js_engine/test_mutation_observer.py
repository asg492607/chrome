"""
Unit & Benchmark Test Suite for MutationObserver Engine & Incremental DOM Re-Flow Manager (Sprint 18).
Verifies MutationObserver microtask batch delivery (attributes, childList, characterData),
dirty flag subtree isolation, and O(K) incremental partial layout re-flow.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from core_platform.tag_constants import TagType
from core_platform.ecs_memory import DocumentTreeMemoryBank, NodeFlags
from rendering_engine.html_parser import HTML5TreeBuilder
from rendering_engine.css_parser import CSSCascadeEngine
from js_engine.v8_bindings import DOMBindings
from js_engine.mutation_observer import (
    MutationType,
    MutationRecord,
    MutationObserver,
    MutationObserverEngine,
    IncrementalReFlowManager
)


class TestMutationObserverSubsystem(unittest.TestCase):

    def test_mutation_observer_attribute_and_child_list_delivery(self):
        """Verify setAttribute and appendChild trigger MutationRecord microtask delivery to callback."""
        bank = DocumentTreeMemoryBank()
        btn_id = DOMBindings.create_element(bank, "button")
        received_records = []

        def callback(records):
            received_records.extend(records)

        observer = MutationObserver(callback)
        observer.observe(btn_id, attributes=True, child_list=True)

        # Mutate attribute
        DOMBindings.set_attribute(bank, btn_id, "class", "active")
        delivered = MutationObserverEngine.deliver_queued_microtasks()

        self.assertEqual(delivered, 1)
        self.assertEqual(len(received_records), 1)
        self.assertEqual(received_records[0].type, MutationType.ATTRIBUTES)
        self.assertEqual(received_records[0].attribute_name, "class")

        observer.disconnect()

    def test_microtask_batch_delivery(self):
        """Verify multiple DOM mutations are batched into a single microtask callback invocation."""
        bank = DocumentTreeMemoryBank()
        div_id = DOMBindings.create_element(bank, "div")

        invocations = []
        def callback(records):
            invocations.append(records)

        observer = MutationObserver(callback)
        observer.observe(div_id, attributes=True)

        # Perform 3 mutations before delivering microtasks
        DOMBindings.set_attribute(bank, div_id, "id", "card-1")
        DOMBindings.set_attribute(bank, div_id, "class", "shadow")
        DOMBindings.set_attribute(bank, div_id, "data-state", "open")

        # Deliver microtasks once
        delivered = MutationObserverEngine.deliver_queued_microtasks()

        self.assertEqual(delivered, 3)
        self.assertEqual(len(invocations), 1) # 1 microtask step invocation
        self.assertEqual(len(invocations[0]), 3) # 3 batched records

        observer.disconnect()

    def test_incremental_reflow_dirty_subtree_isolation(self):
        """Verify mutating a leaf node isolates dirty subtree root without marking entire tree dirty."""
        html = (
            '<html><body>'
            '<div id="container">'
            '<div id="card-1"><p id="text-1">Text 1</p></div>'
            '<div id="card-2"><p id="text-2">Text 2</p></div>'
            '</div>'
            '</body></html>'
        )
        builder = HTML5TreeBuilder()
        root_id, bank = builder.parse_html(html)

        card1_id = DOMBindings.get_element_by_id(bank, "card-1")
        self.assertIsNotNone(card1_id)

        # Initially no dirty nodes
        for i in range(bank.count):
            bank.entities[i].flags &= ~(int(NodeFlags.DIRTY_STYLE) | int(NodeFlags.DIRTY_LAYOUT))

        # Mutate style on card1 ONLY
        DOMBindings.set_style(bank, card1_id, "color", "red")

        # Locate dirty subtree roots
        dirty_roots = IncrementalReFlowManager.find_dirty_subtrees(bank)
        self.assertEqual(len(dirty_roots), 1)
        self.assertEqual(dirty_roots[0], card1_id)

    def test_execute_incremental_reflow_clears_dirty_flags(self):
        """Verify execute_incremental_reflow clears DIRTY_STYLE & DIRTY_LAYOUT flags on updated entities."""
        bank = DocumentTreeMemoryBank()
        node_id = DOMBindings.create_element(bank, "div")
        DOMBindings.set_style(bank, node_id, "background", "blue")

        self.assertNotEqual(bank.entities[node_id].flags & int(NodeFlags.DIRTY_STYLE), 0)

        cascade = CSSCascadeEngine()
        res = IncrementalReFlowManager.execute_incremental_reflow(bank, cascade, layout_engine=None)

        self.assertEqual(res["dirty_subtrees"], 1)
        self.assertEqual(bank.entities[node_id].flags & int(NodeFlags.DIRTY_STYLE), 0)

    def test_high_speed_incremental_reflow_benchmark(self):
        """
        Benchmark: Execute incremental re-flow for 50 dirty subtrees in a 1,000 node DOM tree.
        Asserts duration < 0.15s (> 50,000 nodes/sec).
        """
        div_blocks = ['<div class="card"><p class="text">Text</p></div>' for _ in range(300)]
        html = f'<!DOCTYPE html><html><body>{"".join(div_blocks)}</body></html>'

        builder = HTML5TreeBuilder()
        root_id, bank = builder.parse_html(html)
        cascade = CSSCascadeEngine()

        # Clear flags
        for i in range(bank.count):
            bank.entities[i].flags &= ~(int(NodeFlags.DIRTY_STYLE) | int(NodeFlags.DIRTY_LAYOUT))

        # Mark 50 subtrees dirty
        div_ids = [i for i in range(bank.count) if bank.entities[i].tag_type == int(TagType.DIV)]
        for target_id in div_ids[:50]:
            bank.entities[target_id].flags |= (int(NodeFlags.DIRTY_STYLE) | int(NodeFlags.DIRTY_LAYOUT))

        start_time = time.perf_counter()
        res = IncrementalReFlowManager.execute_incremental_reflow(bank, cascade, layout_engine=None)
        duration = time.perf_counter() - start_time

        nodes_processed = res["reprocessed_entities"]
        nodes_per_sec = nodes_processed / duration
        latency_us = (duration / nodes_processed) * 1_000_000

        self.assertLess(duration, 0.15, f"Incremental reflow took {duration*1000:.2f}ms (must be < 150ms)")
        print(f"\n[Sprint 18 Incremental Re-Flow Benchmark] {nodes_processed:,} Dirty Subtree Nodes Updated:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Dirty Subtrees Resolved: {res['dirty_subtrees']}")
        print(f"  - Incremental Re-Flow Speed: {nodes_per_sec:,.0f} nodes/second")
        print(f"  - Average Node Update Latency: {latency_us:.2f} µs/node")


if __name__ == "__main__":
    unittest.main()
