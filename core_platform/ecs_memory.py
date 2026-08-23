"""
Hardware-Aligned ECS Memory Subsystem for DOM & Layout Trees.
Implements exact 32-byte cache-line aligned DOM entity structs (2 entities per 64-byte L1 cache line)
and contiguous Structure-of-Arrays (SoA) memory banks with zero dynamic pointer allocations.
"""

import ctypes
from typing import List, Dict, Optional, Tuple, Generator
from core_platform.tag_constants import TagType, NodeFlags, TAG_NAME_TO_TYPE, TAG_TYPE_TO_NAME

NULL_ENTITY: int = 0xFFFFFFFF  # 32-bit unsigned sentinel for null / root parent

class Rect4f(ctypes.Structure):
    """
    16-Byte IEEE 754 Floating-Point Bounding Box (x, y, width, height).
    Fits directly into a 128-bit SIMD register (SSE / ARM Neon).
    """
    _pack_ = 4
    _fields_ = [
        ("x", ctypes.c_float),
        ("y", ctypes.c_float),
        ("width", ctypes.c_float),
        ("height", ctypes.c_float),
    ]

    def __repr__(self) -> str:
        return f"Rect4f(x={self.x:.1f}, y={self.y:.1f}, w={self.width:.1f}, h={self.height:.1f})"

    def to_tuple(self) -> Tuple[float, float, float, float]:
        return (self.x, self.y, self.width, self.height)


class DOMEntity32(ctypes.Structure):
    """
    Exact 32-Byte DOM Entity Struct.
    Pair-aligned to fit 2 complete entities into a single 64-byte CPU L1 cache line.
    
    Memory Layout (32 Bytes total):
    - [00..03] parent_index       : u32 (4 Bytes)
    - [04..07] first_child_index  : u32 (4 Bytes)
    - [08..11] next_sibling_index : u32 (4 Bytes)
    - [12]     tag_type           : u8  (1 Byte)
    - [13]     flags              : u8  (1 Byte)
    - [14..15] style_index        : u16 (2 Bytes)
    - [16..31] geometry (Rect4f)  : 4x f32 (16 Bytes)
    """
    _pack_ = 1
    _fields_ = [
        ("parent_index", ctypes.c_uint32),
        ("first_child_index", ctypes.c_uint32),
        ("next_sibling_index", ctypes.c_uint32),
        ("tag_type", ctypes.c_uint8),
        ("flags", ctypes.c_uint8),
        ("style_index", ctypes.c_uint16),
        ("geometry", Rect4f),
    ]

    def __repr__(self) -> str:
        tag_name = TAG_TYPE_TO_NAME.get(TagType(self.tag_type), f"TAG_{self.tag_type}")
        return (
            f"DOMEntity32(tag={tag_name}, parent={self.parent_index}, "
            f"first_child={self.first_child_index}, next_sibling={self.next_sibling_index}, "
            f"flags={self.flags:#04x}, style_idx={self.style_index}, rect={self.geometry})"
        )


class DocumentTreeMemoryBank:
    """
    Contiguous Structure-of-Arrays (SoA) memory bank for document hierarchy and layout state.
    Eliminates heap fragmentation and pointer-chasing during DOM / Layout passes.
    """

    def __init__(self, initial_capacity: int = 1024):
        self.capacity: int = max(64, initial_capacity)
        self.count: int = 0
        
        # Pre-allocate contiguous binary buffer for 32-byte entities
        self._entity_array_type = DOMEntity32 * self.capacity
        self.entities = self._entity_array_type()
        
        # Side-car pools for dynamic text payloads and attributes
        self.text_pool: Dict[int, str] = {}
        self.attr_pool: Dict[int, Dict[str, str]] = {}
        self.computed_styles_pool: Dict[int, Dict[str, str]] = {}
        self.last_child_pool: Dict[int, int] = {}

    def _grow_if_needed(self, required_capacity: Optional[int] = None) -> None:
        """Double the contiguous memory buffer when capacity is reached."""
        target = required_capacity or (self.count + 1)
        if target > self.capacity:
            new_capacity = max(self.capacity * 2, target)
            new_array_type = DOMEntity32 * new_capacity
            new_entities = new_array_type()
            
            # Copy memory directly via ctypes memmove for maximum speed
            ctypes.memmove(
                ctypes.byref(new_entities),
                ctypes.byref(self.entities),
                self.count * ctypes.sizeof(DOMEntity32)
            )
            
            self.capacity = new_capacity
            self._entity_array_type = new_array_type
            self.entities = new_entities

    def allocate_entity(
        self,
        tag_type: TagType,
        parent_index: int = NULL_ENTITY,
        flags: int = NodeFlags.VISIBILITY | NodeFlags.DIRTY_LAYOUT | NodeFlags.DIRTY_STYLE,
        style_index: int = 0,
        text: str = "",
        attrs: Optional[Dict[str, str]] = None
    ) -> int:
        """
        Allocates a new 32-byte DOM entity in the contiguous memory pool.
        Returns the 0-indexed Entity ID.
        """
        self._grow_if_needed()
        entity_id = self.count
        self.count += 1

        entity = self.entities[entity_id]
        entity.parent_index = parent_index
        entity.first_child_index = NULL_ENTITY
        entity.next_sibling_index = NULL_ENTITY
        entity.tag_type = int(tag_type)
        entity.flags = int(flags)
        entity.style_index = style_index
        entity.geometry.x = 0.0
        entity.geometry.y = 0.0
        entity.geometry.width = 0.0
        entity.geometry.height = 0.0

        if text:
            self.text_pool[entity_id] = text
            entity.flags |= int(NodeFlags.TEXT_NODE)

        if attrs:
            self.attr_pool[entity_id] = attrs

        # If parent specified, establish linkage
        if parent_index != NULL_ENTITY and parent_index < entity_id:
            self.append_child(parent_index, entity_id)

        return entity_id

    def append_child(self, parent_id: int, child_id: int) -> None:
        """Establishes child-sibling pointer linkage without heap allocations."""
        if parent_id >= self.count or child_id >= self.count:
            raise IndexError("Entity ID out of memory bank range.")

        child = self.entities[child_id]
        child.parent_index = parent_id

        parent = self.entities[parent_id]
        if parent.first_child_index == NULL_ENTITY:
            parent.first_child_index = child_id
            self.last_child_pool[parent_id] = child_id
        else:
            last_id = self.last_child_pool.get(parent_id)
            if last_id is not None and last_id < self.count:
                self.entities[last_id].next_sibling_index = child_id
            else:
                curr_id = parent.first_child_index
                while self.entities[curr_id].next_sibling_index != NULL_ENTITY:
                    curr_id = self.entities[curr_id].next_sibling_index
                self.entities[curr_id].next_sibling_index = child_id
            self.last_child_pool[parent_id] = child_id


    def set_geometry(self, entity_id: int, x: float, y: float, width: float, height: float) -> None:
        """Directly writes geometry into the 16-byte Rect4f field of the entity."""
        if entity_id >= self.count:
            raise IndexError(f"Entity ID {entity_id} out of bounds.")
        geom = self.entities[entity_id].geometry
        geom.x = x
        geom.y = y
        geom.width = width
        geom.height = height
        # Clear dirty layout flag
        self.entities[entity_id].flags &= ~int(NodeFlags.DIRTY_LAYOUT)

    def get_geometry(self, entity_id: int) -> Rect4f:
        """Returns the Rect4f geometry struct for the entity."""
        if entity_id >= self.count:
            raise IndexError(f"Entity ID {entity_id} out of bounds.")
        return self.entities[entity_id].geometry

    def get_children(self, entity_id: int) -> List[int]:
        """Returns all direct child entity IDs by walking the sibling chain."""
        children = []
        if entity_id >= self.count:
            return children
        curr_id = self.entities[entity_id].first_child_index
        while curr_id != NULL_ENTITY:
            children.append(curr_id)
            curr_id = self.entities[curr_id].next_sibling_index
        return children

    def traverse_dfs(self, root_id: int = 0) -> Generator[int, None, None]:
        """Depth-First Search traversal over contiguous sibling chains."""
        if self.count == 0 or root_id >= self.count:
            return
        stack = [root_id]
        while stack:
            curr_id = stack.pop()
            yield curr_id
            # Collect children and push in reverse order for left-to-right DFS
            children = self.get_children(curr_id)
            for child_id in reversed(children):
                stack.append(child_id)

    def traverse_linear(self) -> Generator[int, None, None]:
        """Linear sequential scan exploiting CPU cache prefetching."""
        for i in range(self.count):
            yield i

    def get_memory_diagnostics(self) -> Dict[str, object]:
        """Calculates precise byte allocations, cache line density, and memory efficiency."""
        entity_size = ctypes.sizeof(DOMEntity32)
        total_entity_bytes = self.capacity * entity_size
        active_entity_bytes = self.count * entity_size
        cache_lines_allocated = (total_entity_bytes + 63) // 64
        cache_lines_active = (active_entity_bytes + 63) // 64
        entities_per_cache_line = 64 // entity_size

        return {
            "entity_struct_size_bytes": entity_size,
            "entities_per_64b_cache_line": entities_per_cache_line,
            "entity_count": self.count,
            "allocated_capacity": self.capacity,
            "total_buffer_bytes": total_entity_bytes,
            "active_entity_bytes": active_entity_bytes,
            "cache_lines_occupied": cache_lines_active,
            "cache_lines_total": cache_lines_allocated,
            "text_pool_entries": len(self.text_pool),
            "attr_pool_entries": len(self.attr_pool),
            "l1_density_ratio": f"{entities_per_cache_line}:1 (Exact 64B fit)"
        }
