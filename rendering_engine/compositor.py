"""
Compositing Layer Tree & GPU Texture Upload Pipeline.
Implements layer promotion heuristics (transforms, opacity, scrolling), hardware texture allocation,
VRAM memory tracking, and GPU layer compositing with opacity blending.
"""

import sys
import os
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core_platform.ecs_memory import DocumentTreeMemoryBank, NodeFlags
from core_platform.tag_constants import TagType
from rendering_engine.rasterizer import RGBABuffer, DisplayList, DisplayListGenerator, SoftwareRasterizer


class LayerType(Enum):
    ROOT = auto()
    SCROLL = auto()
    TRANSFORM = auto()
    CANVAS = auto()
    GPU_TILE = auto()


class CompositingLayer:
    """Represents an isolated GPU compositing layer."""
    def __init__(self, layer_id: int, node_id: int, layer_type: LayerType):
        self.layer_id = layer_id
        self.node_id = node_id
        self.layer_type = layer_type
        self.bounds: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
        self.opacity: float = 1.0
        self.gpu_texture_id: Optional[int] = None
        self.display_list: Optional[DisplayList] = None
        self.children: List["CompositingLayer"] = []

    def add_child(self, child: "CompositingLayer") -> None:
        self.children.append(child)

    def __repr__(self) -> str:
        return f"CompLayer(ID={self.layer_id}, node={self.node_id}, type={self.layer_type.name}, opacity={self.opacity:.2f})"


class CompositingTreeBuilder:
    """
    Evaluates DOM nodes and computed styles for GPU layer promotion.
    Constructs a visual CompositingLayer tree for hardware compositing.
    """

    _next_layer_id = 1

    @classmethod
    def _alloc_layer_id(cls) -> int:
        lid = cls._next_layer_id
        cls._next_layer_id += 1
        return lid

    @classmethod
    def should_promote_to_layer(cls, bank: DocumentTreeMemoryBank, node_id: int) -> Tuple[bool, LayerType, float]:
        """Evaluates layer promotion heuristics: transform, opacity < 1.0, will-change, overflow: scroll."""
        styles = bank.computed_styles_pool.get(node_id, {})
        entity = bank.entities[node_id]

        # 1. Canvas or Video Element
        if entity.tag_type in (int(TagType.CANVAS), int(TagType.VIDEO)):
            return (True, LayerType.CANVAS, 1.0)

        # 2. Transform property
        if "transform" in styles and styles["transform"] != "none":
            return (True, LayerType.TRANSFORM, 1.0)

        # 3. Opacity < 1.0
        raw_opacity = styles.get("opacity", "1.0").strip()
        try:
            op_val = float(raw_opacity)
            if op_val < 1.0:
                return (True, LayerType.GPU_TILE, op_val)
        except ValueError:
            pass

        # 4. Overflow: Scroll / Auto
        overflow = styles.get("overflow", "").strip().lower()
        if overflow in ("scroll", "auto"):
            return (True, LayerType.SCROLL, 1.0)

        # 5. Will-Change property
        if "will-change" in styles:
            return (True, LayerType.GPU_TILE, 1.0)

        return (False, LayerType.GPU_TILE, 1.0)

    @classmethod
    def build_layer_tree(cls, bank: DocumentTreeMemoryBank, root_id: int) -> CompositingLayer:
        """Constructs the root CompositingLayer tree for the entire DOM Memory Bank."""
        root_layer = CompositingLayer(cls._alloc_layer_id(), root_id, LayerType.ROOT)
        if root_id < bank.count:
            geom = bank.entities[root_id].geometry
            root_layer.bounds = (geom.x, geom.y, geom.width, geom.height)

        cls._traverse_and_promote(bank, root_id, root_layer)
        return root_layer

    @classmethod
    def _traverse_and_promote(
        cls,
        bank: DocumentTreeMemoryBank,
        node_id: int,
        parent_layer: CompositingLayer
    ) -> None:
        if node_id >= bank.count:
            return

        entity = bank.entities[node_id]
        child_id = entity.first_child_index

        while child_id != 0xFFFFFFFF and child_id < bank.count:
            promote, l_type, opacity = cls.should_promote_to_layer(bank, child_id)
            c_geom = bank.entities[child_id].geometry

            if promote:
                new_layer = CompositingLayer(cls._alloc_layer_id(), child_id, l_type)
                new_layer.bounds = (c_geom.x, c_geom.y, c_geom.width, c_geom.height)
                new_layer.opacity = opacity
                parent_layer.add_child(new_layer)
                current_parent = new_layer
            else:
                current_parent = parent_layer

            cls._traverse_and_promote(bank, child_id, current_parent)
            child_id = bank.entities[child_id].next_sibling_index


class GPUTexturePipeline:
    """Simulates high-speed GPU texture allocation, VRAM management, and DMA texture uploads."""
    def __init__(self):
        self.textures: Dict[int, bytearray] = {}
        self.texture_sizes: Dict[int, Tuple[int, int]] = {}
        self.next_texture_id: int = 1
        self.vram_allocated_bytes: int = 0

    def allocate_texture(self, width: int, height: int) -> int:
        """Allocates VRAM storage for a GPU texture slot."""
        tex_id = self.next_texture_id
        self.next_texture_id += 1

        size_bytes = width * height * 4
        self.textures[tex_id] = bytearray(size_bytes)
        self.texture_sizes[tex_id] = (width, height)
        self.vram_allocated_bytes += size_bytes
        return tex_id

    def upload_rgba_texture(self, texture_id: int, rgba_buffer: RGBABuffer) -> int:
        """DMA uploads a rasterized RGBABuffer into target GPU VRAM texture slot."""
        if texture_id not in self.textures:
            return 0

        target_buf = self.textures[texture_id]
        copy_size = min(len(target_buf), len(rgba_buffer.data))
        target_buf[0:copy_size] = rgba_buffer.data[0:copy_size]
        return copy_size


class CompositorEngine:
    """Composites GPU texture layers in z-index order onto the final target frame buffer."""

    @classmethod
    def composite_layers(
        cls,
        root_layer: CompositingLayer,
        gpu_pipeline: GPUTexturePipeline,
        target_buffer: RGBABuffer
    ) -> int:
        """Traverses CompositingLayer tree and composites texture layers into target_buffer."""
        layers_composited = 0
        queue: List[CompositingLayer] = [root_layer]

        while queue:
            curr_layer = queue.pop(0)
            layers_composited += 1

            if curr_layer.gpu_texture_id and curr_layer.gpu_texture_id in gpu_pipeline.textures:
                tex_data = gpu_pipeline.textures[curr_layer.gpu_texture_id]
                tw, th = gpu_pipeline.texture_sizes.get(curr_layer.gpu_texture_id, (100, 100))

                bx = int(round(curr_layer.bounds[0]))
                by = int(round(curr_layer.bounds[1]))

                # Blend GPU texture pixels into target frame buffer
                opacity_mult = curr_layer.opacity
                for y in range(min(th, target_buffer.height - by)):
                    for x in range(min(tw, target_buffer.width - bx)):
                        src_off = (y * tw + x) * 4
                        sr = tex_data[src_off]
                        sg = tex_data[src_off + 1]
                        sb = tex_data[src_off + 2]
                        sa = int(tex_data[src_off + 3] * opacity_mult)

                        if sa > 0:
                            target_buffer.set_pixel(bx + x, by + y, sr, sg, sb, sa)

            queue.extend(curr_layer.children)

        return layers_composited
