"""
Flexbox Layout Engine & Multi-Axis Alignment System.
Implements W3C CSS Flexible Box Layout module, supporting flex-direction (row/column),
flex-grow free-space distribution, justify-content main-axis alignment, align-items cross-axis alignment,
and direct 16-byte Rect4f memory packing into DocumentTreeMemoryBank.
"""

import sys
import os
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core_platform.ecs_memory import DocumentTreeMemoryBank
from rendering_engine.layout_engine import LayoutNode, LayoutNodeType, BoxDimensions


class FlexDirection(Enum):
    ROW = auto()
    COLUMN = auto()
    ROW_REVERSE = auto()
    COLUMN_REVERSE = auto()


class JustifyContent(Enum):
    FLEX_START = auto()
    FLEX_END = auto()
    CENTER = auto()
    SPACE_BETWEEN = auto()
    SPACE_AROUND = auto()
    SPACE_EVENLY = auto()


class AlignItems(Enum):
    FLEX_START = auto()
    FLEX_END = auto()
    CENTER = auto()
    STRETCH = auto()


class FlexItem:
    """Represents a single child item inside a flex container."""
    def __init__(self, layout_node: LayoutNode, styles: Dict[str, str]):
        self.layout_node = layout_node
        self.styles = styles

        # Parse flex-grow factor
        raw_grow = styles.get("flex-grow", styles.get("flex", "0")).strip()
        try:
            self.flex_grow = float(raw_grow.split()[0])
        except (ValueError, IndexError):
            self.flex_grow = 0.0

        self.base_main_size: float = 0.0
        self.target_main_size: float = 0.0
        self.cross_size: float = 0.0
        self.main_pos: float = 0.0
        self.cross_pos: float = 0.0


class FlexboxEngine:
    """
    W3C Flexbox Layout Engine for multi-axis layout calculation and space distribution.
    """

    @classmethod
    def is_flex_container(cls, styles: Dict[str, str]) -> bool:
        """Returns True if element style specifies display: flex or inline-flex."""
        disp = styles.get("display", "").strip().lower()
        return disp in ("flex", "inline-flex")

    @classmethod
    def parse_flex_direction(cls, styles: Dict[str, str]) -> FlexDirection:
        val = styles.get("flex-direction", "row").strip().lower()
        if val == "column":
            return FlexDirection.COLUMN
        elif val == "row-reverse":
            return FlexDirection.ROW_REVERSE
        elif val == "column-reverse":
            return FlexDirection.COLUMN_REVERSE
        return FlexDirection.ROW

    @classmethod
    def parse_justify_content(cls, styles: Dict[str, str]) -> JustifyContent:
        val = styles.get("justify-content", "flex-start").strip().lower()
        if val in ("flex-end", "end"):
            return JustifyContent.FLEX_END
        elif val == "center":
            return JustifyContent.CENTER
        elif val == "space-between":
            return JustifyContent.SPACE_BETWEEN
        elif val == "space-around":
            return JustifyContent.SPACE_AROUND
        elif val == "space-evenly":
            return JustifyContent.SPACE_EVENLY
        return JustifyContent.FLEX_START

    @classmethod
    def parse_align_items(cls, styles: Dict[str, str]) -> AlignItems:
        val = styles.get("align-items", "stretch").strip().lower()
        if val in ("flex-start", "start"):
            return AlignItems.FLEX_START
        elif val in ("flex-end", "end"):
            return AlignItems.FLEX_END
        elif val == "center":
            return AlignItems.CENTER
        return AlignItems.STRETCH

    @classmethod
    def layout_flex_container(
        cls,
        bank: DocumentTreeMemoryBank,
        flex_node: LayoutNode,
        containment_width: float,
        containment_height: float
    ) -> None:
        """Computes Flexbox layout geometry for main and cross axes."""
        styles = bank.computed_styles_pool.get(flex_node.entity_id, {})
        direction = cls.parse_flex_direction(styles)
        justify = cls.parse_justify_content(styles)
        align = cls.parse_align_items(styles)

        is_row = direction in (FlexDirection.ROW, FlexDirection.ROW_REVERSE)

        # 1. Container Main & Cross Dimensions
        container_main_size = containment_width if is_row else containment_height
        container_cross_size = containment_height if is_row else containment_width

        # 2. Build FlexItem wrappers for children
        items: List[FlexItem] = []
        for child in flex_node.children:
            c_styles = bank.computed_styles_pool.get(child.entity_id, {})
            item = FlexItem(child, c_styles)

            # Base main size from width/height or default
            if is_row:
                raw_w = c_styles.get("width", "")
                item.base_main_size = float(raw_w.replace("px", "")) if raw_w and raw_w.replace("px", "").replace(".", "", 1).isdigit() else 100.0
                raw_h = c_styles.get("height", "")
                item.cross_size = float(raw_h.replace("px", "")) if raw_h and raw_h.replace("px", "").replace(".", "", 1).isdigit() else 40.0
            else:
                raw_h = c_styles.get("height", "")
                item.base_main_size = float(raw_h.replace("px", "")) if raw_h and raw_h.replace("px", "").replace(".", "", 1).isdigit() else 40.0
                raw_w = c_styles.get("width", "")
                item.cross_size = float(raw_w.replace("px", "")) if raw_w and raw_w.replace("px", "").replace(".", "", 1).isdigit() else 100.0

            item.target_main_size = item.base_main_size
            items.append(item)

        if not items:
            return

        # Reverse items if ROW_REVERSE or COLUMN_REVERSE
        if direction in (FlexDirection.ROW_REVERSE, FlexDirection.COLUMN_REVERSE):
            items.reverse()

        # 3. Calculate Free Space & Flex-Grow Distribution
        total_base_main = sum(item.base_main_size for item in items)
        free_space = container_main_size - total_base_main
        total_grow = sum(item.flex_grow for item in items)

        if free_space > 0 and total_grow > 0:
            for item in items:
                if item.flex_grow > 0:
                    item.target_main_size = item.base_main_size + (free_space * (item.flex_grow / total_grow))
            used_main_size = container_main_size
        else:
            used_main_size = total_base_main

        # 4. Main-Axis Justify Content Calculation
        remaining_main = container_main_size - sum(item.target_main_size for item in items)
        current_main_offset = 0.0
        main_gap = 0.0

        if justify == JustifyContent.FLEX_END:
            current_main_offset = max(0.0, remaining_main)
        elif justify == JustifyContent.CENTER:
            current_main_offset = max(0.0, remaining_main / 2.0)
        elif justify == JustifyContent.SPACE_BETWEEN and len(items) > 1:
            main_gap = max(0.0, remaining_main / (len(items) - 1))
        elif justify == JustifyContent.SPACE_AROUND and len(items) > 0:
            main_gap = max(0.0, remaining_main / len(items))
            current_main_offset = main_gap / 2.0
        elif justify == JustifyContent.SPACE_EVENLY and len(items) > 0:
            main_gap = max(0.0, remaining_main / (len(items) + 1))
            current_main_offset = main_gap

        # 5. Position Items & Write Geometry directly into ECS
        for item in items:
            item.main_pos = current_main_offset
            current_main_offset += item.target_main_size + main_gap

            # Cross-Axis Alignment
            if align == AlignItems.FLEX_END:
                item.cross_pos = max(0.0, container_cross_size - item.cross_size)
            elif align == AlignItems.CENTER:
                item.cross_pos = max(0.0, (container_cross_size - item.cross_size) / 2.0)
            elif align == AlignItems.STRETCH:
                item.cross_pos = 0.0
                item.cross_size = container_cross_size
            else: # FLEX_START
                item.cross_pos = 0.0

            # Convert Main/Cross to absolute (x, y, width, height)
            if is_row:
                x = flex_node.dimensions.x + item.main_pos
                y = flex_node.dimensions.y + item.cross_pos
                w = item.target_main_size
                h = item.cross_size
            else:
                x = flex_node.dimensions.x + item.cross_pos
                y = flex_node.dimensions.y + item.main_pos
                w = item.cross_size
                h = item.target_main_size

            # Update LayoutNode dimensions
            item.layout_node.dimensions.x = x
            item.layout_node.dimensions.y = y
            item.layout_node.dimensions.width = w
            item.layout_node.dimensions.height = h

            # Write directly into 16-byte Rect4f field of DOM entity slot
            bank.set_geometry(item.layout_node.entity_id, x, y, w, h)
