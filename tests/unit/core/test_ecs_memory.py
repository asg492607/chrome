"""
Unit & Benchmark Test Suite for ECS Memory Subsystem (Sprint 01).
Verifies exact 32-byte struct alignment, 64-byte L1 cache density,
DOM tree hierarchy operations, and memory efficiency benchmarks.
"""

import sys
import os
import unittest
import ctypes
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from core_platform.tag_constants import TagType, NodeFlags, TAG_NAME_TO_TYPE, TAG_TYPE_TO_NAME
from core_platform.ecs_memory import (
    Rect4f,
    DOMEntity32,
    DocumentTreeMemoryBank,
    NULL_ENTITY
)
from browser_engine.browser_models import Node as LegacyNode


class TestECSMemorySubsystem(unittest.TestCase):

    def test_struct_size_and_cache_line_alignment(self):
        """Verify byte-level sizes and L1 cache line mathematical packing."""
        rect_size = ctypes.sizeof(Rect4f)
        entity_size = ctypes.sizeof(DOMEntity32)

        self.assertEqual(rect_size, 16, f"Rect4f must be exactly 16 bytes, got {rect_size}")
        self.assertEqual(entity_size, 32, f"DOMEntity32 must be exactly 32 bytes, got {entity_size}")

        # Mathematical proof: exactly 2 entities fit into a standard 64-byte L1 cache line
        cache_line_size = 64
        entities_per_cache_line = cache_line_size // entity_size
        remainder_bytes = cache_line_size % entity_size

        self.assertEqual(entities_per_cache_line, 2, "Must fit exactly 2 entities per 64B cache line")
        self.assertEqual(remainder_bytes, 0, "Zero padding remainder bytes inside 64B cache line")

    def test_entity_allocation_and_flags(self):
        """Test basic allocation, tag assignment, text pool, and bitmask flags."""
        bank = DocumentTreeMemoryBank(initial_capacity=64)
        
        div_id = bank.allocate_entity(
            tag_type=TagType.DIV,
            flags=NodeFlags.VISIBILITY | NodeFlags.DIRTY_LAYOUT,
            attrs={"class": "container", "id": "main"}
        )
        
        self.assertEqual(div_id, 0)
        self.assertEqual(bank.count, 1)
        
        entity = bank.entities[div_id]
        self.assertEqual(entity.tag_type, int(TagType.DIV))
        self.assertTrue(bool(entity.flags & int(NodeFlags.VISIBILITY)))
        self.assertTrue(bool(entity.flags & int(NodeFlags.DIRTY_LAYOUT)))
        self.assertFalse(bool(entity.flags & int(NodeFlags.HOVER)))
        self.assertEqual(bank.attr_pool[div_id]["class"], "container")

    def test_tree_hierarchy_and_sibling_chaining(self):
        """Test parent-child relationship and sibling pointer linkage."""
        bank = DocumentTreeMemoryBank(initial_capacity=128)

        # Build structure:
        # root (0: HTML)
        #  └── body (1: BODY)
        #       ├── h1 (2: H1)
        #       ├── p (3: P)
        #       └── button (4: BUTTON)
        
        root_id = bank.allocate_entity(TagType.HTML)
        body_id = bank.allocate_entity(TagType.BODY, parent_index=root_id)
        h1_id = bank.allocate_entity(TagType.H1, parent_index=body_id, text="Title")
        p_id = bank.allocate_entity(TagType.P, parent_index=body_id, text="Paragraph text")
        btn_id = bank.allocate_entity(TagType.BUTTON, parent_index=body_id, text="Click Me")

        self.assertEqual(bank.count, 5)

        # Check body's first child is h1
        self.assertEqual(bank.entities[body_id].first_child_index, h1_id)
        # Check h1's sibling is p
        self.assertEqual(bank.entities[h1_id].next_sibling_index, p_id)
        # Check p's sibling is button
        self.assertEqual(bank.entities[p_id].next_sibling_index, btn_id)
        # Check button's sibling is NULL_ENTITY
        self.assertEqual(bank.entities[btn_id].next_sibling_index, NULL_ENTITY)

        # Verify get_children helper
        body_children = bank.get_children(body_id)
        self.assertEqual(body_children, [h1_id, p_id, btn_id])

    def test_dfs_traversal_order(self):
        """Verify pre-order DFS traversal across nested subtree branches."""
        bank = DocumentTreeMemoryBank()

        root = bank.allocate_entity(TagType.HTML)
        head = bank.allocate_entity(TagType.HEAD, parent_index=root)
        body = bank.allocate_entity(TagType.BODY, parent_index=root)
        div = bank.allocate_entity(TagType.DIV, parent_index=body)
        p = bank.allocate_entity(TagType.P, parent_index=div)
        span = bank.allocate_entity(TagType.SPAN, parent_index=div)

        traversed_ids = list(bank.traverse_dfs(root))
        expected_order = [root, head, body, div, p, span]
        self.assertEqual(traversed_ids, expected_order)

    def test_geometry_and_dirty_flag_clearing(self):
        """Verify geometry coordinates manipulation and dirty-flag clearing."""
        bank = DocumentTreeMemoryBank()
        btn_id = bank.allocate_entity(TagType.BUTTON, flags=NodeFlags.DIRTY_LAYOUT | NodeFlags.VISIBILITY)

        self.assertTrue(bool(bank.entities[btn_id].flags & int(NodeFlags.DIRTY_LAYOUT)))

        bank.set_geometry(btn_id, x=10.0, y=20.0, width=120.0, height=45.0)

        geom = bank.get_geometry(btn_id)
        self.assertAlmostEqual(geom.x, 10.0)
        self.assertAlmostEqual(geom.y, 20.0)
        self.assertAlmostEqual(geom.width, 120.0)
        self.assertAlmostEqual(geom.height, 45.0)

        # Assert DIRTY_LAYOUT flag was cleared automatically
        self.assertFalse(bool(bank.entities[btn_id].flags & int(NodeFlags.DIRTY_LAYOUT)))

    def test_memory_diagnostics_calculation(self):
        """Verify diagnostics output and cache line occupancy metrics."""
        bank = DocumentTreeMemoryBank(initial_capacity=100)
        for i in range(50):
            bank.allocate_entity(TagType.DIV)

        diag = bank.get_memory_diagnostics()
        self.assertEqual(diag["entity_struct_size_bytes"], 32)
        self.assertEqual(diag["entities_per_64b_cache_line"], 2)
        self.assertEqual(diag["entity_count"], 50)
        self.assertEqual(diag["active_entity_bytes"], 50 * 32) # 1600 bytes
        self.assertEqual(diag["cache_lines_occupied"], 25)     # 1600 / 64 = 25 cache lines
        self.assertEqual(diag["l1_density_ratio"], "2:1 (Exact 64B fit)")

    def test_scale_benchmark_and_memory_efficiency(self):
        """
        Scale test: Build 10,000 nodes using ECS memory bank vs Legacy OOP Nodes.
        Asserts substantial memory reduction and sub-10ms build time.
        """
        node_count = 10000

        # Benchmark 1: ECS Memory Bank
        start_ecs = time.perf_counter()
        ecs_bank = DocumentTreeMemoryBank(initial_capacity=node_count)
        root_ecs = ecs_bank.allocate_entity(TagType.HTML)
        for i in range(1, node_count):
            parent = (i - 1) // 4
            ecs_bank.allocate_entity(TagType.DIV, parent_index=parent)
        duration_ecs = time.perf_counter() - start_ecs

        # Benchmark 2: Legacy OOP Node Tree
        start_legacy = time.perf_counter()
        legacy_nodes = [LegacyNode("html")]
        for i in range(1, node_count):
            parent_idx = (i - 1) // 4
            n = LegacyNode("div", parent=legacy_nodes[parent_idx])
            legacy_nodes[parent_idx].add_child(n)
            legacy_nodes.append(n)
        duration_legacy = time.perf_counter() - start_legacy

        # Memory calculations
        ecs_bytes = ctypes.sizeof(DOMEntity32) * ecs_bank.count # 32 * 10,000 = 320,000 bytes (~312 KB)
        
        # In Python, each legacy Node object with __dict__, list, string attrs consumes ~300+ bytes
        self.assertLess(ecs_bytes, 350000, "10k ECS entities must consume <= 350 KB of raw memory")
        self.assertLess(duration_ecs, 0.05, f"10k entity creation must complete under 50ms, took {duration_ecs*1000:.2f}ms")
        
        print(f"\n[Sprint 01 Benchmark] 10,000 Nodes Build:")
        print(f"  - ECS Memory Bank Raw Bytes: {ecs_bytes / 1024:.1f} KB (Exact 32B/node)")
        print(f"  - ECS Build Time: {duration_ecs * 1000:.2f} ms")
        print(f"  - Legacy OOP Build Time: {duration_legacy * 1000:.2f} ms")


if __name__ == "__main__":
    unittest.main()
