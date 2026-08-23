"""
Box Model Geometry & Layout Tree Builder Engine.
Calculates content box, padding, border, and margin dimensions, constructs the visual Layout Tree,
and packs computed 16-byte Rect4f bounding boxes (x, y, width, height) directly into DocumentTreeMemoryBank.
"""

import sys
import os
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core_platform.tag_constants import TagType
from core_platform.ecs_memory import DocumentTreeMemoryBank, NodeFlags


class EdgeDimensions:
    """Represents Top, Right, Bottom, Left edge values (margin, border, padding)."""
    def __init__(self, top: float = 0.0, right: float = 0.0, bottom: float = 0.0, left: float = 0.0):
        self.top = top
        self.right = right
        self.bottom = bottom
        self.left = left

    def __repr__(self) -> str:
        return f"Edge({self.top:.1f}, {self.right:.1f}, {self.bottom:.1f}, {self.left:.1f})"


class BoxDimensions:
    """W3C Standard CSS Box Model Dimensions (Content, Padding, Border, Margin)."""
    def __init__(self):
        # Content Box Position & Size
        self.x: float = 0.0
        self.y: float = 0.0
        self.width: float = 0.0
        self.height: float = 0.0

        # Surrounding Edge Dimensions
        self.padding = EdgeDimensions()
        self.border = EdgeDimensions()
        self.margin = EdgeDimensions()

    def padding_box(self) -> Tuple[float, float, float, float]:
        """Returns (x, y, width, height) for the Padding Box."""
        return (
            self.x - self.padding.left,
            self.y - self.padding.top,
            self.width + self.padding.left + self.padding.right,
            self.height + self.padding.top + self.padding.bottom
        )

    def border_box(self) -> Tuple[float, float, float, float]:
        """Returns (x, y, width, height) for the Border Box."""
        px, py, pw, ph = self.padding_box()
        return (
            px - self.border.left,
            py - self.border.top,
            pw + self.border.left + self.border.right,
            ph + self.border.top + self.border.bottom
        )

    def margin_box(self) -> Tuple[float, float, float, float]:
        """Returns (x, y, width, height) for the Margin Box."""
        bx, by, bw, bh = self.border_box()
        return (
            bx - self.margin.left,
            by - self.margin.top,
            bw + self.margin.left + self.margin.right,
            bh + self.margin.top + self.margin.bottom
        )

    def __repr__(self) -> str:
        return f"Box({self.x:.1f},{self.y:.1f},{self.width:.1f}x{self.height:.1f})"


class LayoutNodeType(Enum):
    """Layout box formatting context type."""
    BLOCK = auto()
    INLINE = auto()
    ANONYMOUS = auto()


class LayoutNode:
    """Represents a single node in the visual layout tree."""
    def __init__(self, entity_id: int, node_type: LayoutNodeType):
        self.entity_id = entity_id
        self.node_type = node_type
        self.dimensions = BoxDimensions()
        self.children: List[LayoutNode] = []

    def add_child(self, child: "LayoutNode") -> None:
        self.children.append(child)

    def __repr__(self) -> str:
        return f"LayoutNode(ID={self.entity_id}, type={self.node_type.name}, dim={self.dimensions})"


class LayoutTreeBuilder:
    """
    Constructs visual LayoutNode hierarchy from DOM entities and computed styles.
    Automatically filters out non-rendered elements (display: none, head, script, style).
    """

    NON_RENDERED_TAGS = {
        int(TagType.HEAD),
        int(TagType.COMMENT)
    }

    @classmethod
    def build_layout_tree(cls, bank: DocumentTreeMemoryBank, root_id: int) -> Optional[LayoutNode]:
        """Recursively builds the layout tree starting at root_id."""
        if root_id >= bank.count:
            return None

        entity = bank.entities[root_id]

        # 1. Filter out non-rendered tag types
        if entity.tag_type in cls.NON_RENDERED_TAGS:
            return None

        # Check tag name for script, style, meta, link
        styles = bank.computed_styles_pool.get(root_id, {})
        attrs = bank.attr_pool.get(root_id, {})
        tag_name = attrs.get("_tag_name", "").lower()
        if tag_name in ("script", "style", "meta", "link"):
            return None

        display = styles.get("display", "block").strip().lower()
        if display == "none":
            return None

        # 3. Determine LayoutNodeType
        node_type = LayoutNodeType.BLOCK if display == "block" else LayoutNodeType.INLINE
        layout_node = LayoutNode(root_id, node_type)

        # 4. Recursively build child layout nodes
        child_id = entity.first_child_index
        while child_id != 0xFFFFFFFF and child_id < bank.count:
            child_layout = cls.build_layout_tree(bank, child_id)
            if child_layout is not None:
                layout_node.add_child(child_layout)
            child_id = bank.entities[child_id].next_sibling_index

        return layout_node


class LayoutEngine:
    """
    Computes Box Model geometry and writes 16-byte Rect4f bounding boxes directly into ECS slots.
    """

    @classmethod
    def parse_pixel_val(cls, val_str: str, default: float = 0.0) -> float:
        """Parses CSS pixel strings (e.g., '16px', '8.5') into floats."""
        if not val_str:
            return default
        cleaned = val_str.replace("px", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return default

    @classmethod
    def layout(
        cls,
        bank: DocumentTreeMemoryBank,
        root_layout: LayoutNode,
        viewport_width: float = 1280.0,
        viewport_height: float = 800.0
    ) -> None:
        """
        Executes layout computation starting at root_layout node.
        Writes computed Rect4f directly into bank.entities[entity_id].geometry.
        """
        if root_layout is None:
            return

        # Initialize Root Node Geometry
        root_layout.dimensions.x = 0.0
        root_layout.dimensions.y = 0.0
        root_layout.dimensions.width = viewport_width
        root_layout.dimensions.height = viewport_height

        cls._layout_block_node(bank, root_layout, containment_width=viewport_width)

    @classmethod
    def _layout_block_node(
        cls,
        bank: DocumentTreeMemoryBank,
        node: LayoutNode,
        containment_width: float
    ) -> None:
        """Computes block formatting context layout and child positions."""
        styles = bank.computed_styles_pool.get(node.entity_id, {})

        # Parse Width (or default to containment width)
        raw_w = styles.get("width", "")
        if raw_w:
            node.dimensions.width = cls.parse_pixel_val(raw_w, containment_width)
        elif node.dimensions.width == 0.0:
            node.dimensions.width = containment_width

        # Parse Margins, Padding
        node.dimensions.margin.top = cls.parse_pixel_val(styles.get("margin-top", styles.get("margin", "")))
        node.dimensions.margin.bottom = cls.parse_pixel_val(styles.get("margin-bottom", styles.get("margin", "")))
        node.dimensions.margin.left = cls.parse_pixel_val(styles.get("margin-left", styles.get("margin", "")))
        node.dimensions.margin.right = cls.parse_pixel_val(styles.get("margin-right", styles.get("margin", "")))

        node.dimensions.padding.top = cls.parse_pixel_val(styles.get("padding-top", styles.get("padding", "")))
        node.dimensions.padding.bottom = cls.parse_pixel_val(styles.get("padding-bottom", styles.get("padding", "")))
        node.dimensions.padding.left = cls.parse_pixel_val(styles.get("padding-left", styles.get("padding", "")))
        node.dimensions.padding.right = cls.parse_pixel_val(styles.get("padding-right", styles.get("padding", "")))

        # Check if flex container
        from rendering_engine.flexbox_engine import FlexboxEngine
        if FlexboxEngine.is_flex_container(styles):
            raw_h = styles.get("height", "")
            containment_h = cls.parse_pixel_val(raw_h, 300.0) if raw_h else 300.0
            node.dimensions.height = containment_h
            FlexboxEngine.layout_flex_container(bank, node, node.dimensions.width, containment_h)
            bank.set_geometry(node.entity_id, node.dimensions.x, node.dimensions.y, node.dimensions.width, containment_h)
            return

        # Layout Children Vertically
        current_y = node.dimensions.y + node.dimensions.padding.top

        content_width = max(0.0, node.dimensions.width - (node.dimensions.padding.left + node.dimensions.padding.right))

        for child in node.children:
            child.dimensions.x = node.dimensions.x + node.dimensions.padding.left + child.dimensions.margin.left
            child.dimensions.y = current_y + child.dimensions.margin.top

            # Recursively layout child
            cls._layout_block_node(bank, child, containment_width=content_width)

            # Advance current_y for vertical block stacking
            child_margin_box_h = child.dimensions.height + child.dimensions.margin.top + child.dimensions.margin.bottom
            current_y += child_margin_box_h

        # Compute Height if not explicitly set
        raw_h = styles.get("height", "")
        if raw_h:
            node.dimensions.height = cls.parse_pixel_val(raw_h)
        else:
            computed_h = current_y - node.dimensions.y
            node.dimensions.height = max(computed_h, 20.0)

        # Write directly into 16-byte Rect4f field of DOM entity slot
        bank.set_geometry(
            node.entity_id,
            node.dimensions.x,
            node.dimensions.y,
            node.dimensions.width,
            node.dimensions.height
        )
