"""
Software Rasterizer & Display List Command Generator Engine.
Translates styled DOM entities and Box Model geometry into ordered Display List draw commands,
and rasterizes pixels directly into raw 32-bit RGBA frame buffers without GPU dependencies.
"""

import sys
import os
import re
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core_platform.ecs_memory import DocumentTreeMemoryBank, NodeFlags
from core_platform.tag_constants import TagType


class DrawCommandType(Enum):
    CLEAR_SCREEN = auto()
    DRAW_RECT = auto()
    DRAW_BORDER = auto()
    DRAW_TEXT = auto()


class DrawCommand:
    """Represents a single rendering draw command."""
    def __init__(
        self,
        command_type: DrawCommandType,
        x: float,
        y: float,
        width: float,
        height: float,
        color: Tuple[int, int, int, int] = (0, 0, 0, 255),
        border_width: float = 0.0,
        text: str = ""
    ):
        self.command_type = command_type
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.color = color
        self.border_width = border_width
        self.text = text

    def __repr__(self) -> str:
        return f"DrawCmd({self.command_type.name}, pos=({self.x:.1f},{self.y:.1f}), size=({self.width:.1f}x{self.height:.1f}), color={self.color})"


class DisplayList:
    """Ordered sequence of draw commands ready for pixel rasterization."""
    def __init__(self):
        self.commands: List[DrawCommand] = []

    def add_command(self, cmd: DrawCommand) -> None:
        self.commands.append(cmd)

    def __len__(self) -> int:
        return len(self.commands)


def parse_css_color(color_str: str) -> Tuple[int, int, int, int]:
    """Parses CSS color strings (#hex, rgb(), rgba(), named colors) into RGBA 4-tuples."""
    if not color_str:
        return (0, 0, 0, 0)
    c = color_str.strip().lower()

    if c in ("transparent", "none"):
        return (0, 0, 0, 0)

    # Named Color Table
    NAMED_COLORS = {
        "white": (255, 255, 255, 255),
        "black": (0, 0, 0, 255),
        "red": (255, 0, 0, 255),
        "green": (0, 128, 0, 255),
        "blue": (0, 0, 255, 255),
        "yellow": (255, 255, 0, 255),
        "gray": (128, 128, 128, 255),
        "grey": (128, 128, 128, 255)
    }
    if c in NAMED_COLORS:
        return NAMED_COLORS[c]

    # Hex Format (#ffffff or #fff)
    if c.startswith('#'):
        hex_val = c[1:]
        if len(hex_val) == 3:
            hex_val = "".join(ch * 2 for ch in hex_val)
        if len(hex_val) == 6:
            try:
                r = int(hex_val[0:2], 16)
                g = int(hex_val[2:4], 16)
                b = int(hex_val[4:6], 16)
                return (r, g, b, 255)
            except ValueError:
                return (0, 0, 0, 255)

    # RGB / RGBA Format
    rgb_match = re.match(r'rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)', c)
    if rgb_match:
        r = int(rgb_match.group(1))
        g = int(rgb_match.group(2))
        b = int(rgb_match.group(3))
        a_str = rgb_match.group(4)
        a = int(float(a_str) * 255) if a_str else 255
        return (r, g, b, a)

    return (0, 0, 0, 255)


class DisplayListGenerator:
    """Translates DOM entities and computed Box Model geometry into ordered Display Lists."""

    @classmethod
    def generate_display_list(cls, bank: DocumentTreeMemoryBank, root_id: int) -> DisplayList:
        display_list = DisplayList()
        display_list.add_command(DrawCommand(DrawCommandType.CLEAR_SCREEN, 0, 0, 1280, 800, color=(255, 255, 255, 255)))

        cls._traverse_and_emit(bank, root_id, display_list)
        return display_list

    @classmethod
    def _traverse_and_emit(cls, bank: DocumentTreeMemoryBank, node_id: int, display_list: DisplayList) -> None:
        if node_id >= bank.count:
            return

        entity = bank.entities[node_id]
        geom = entity.geometry
        styles = bank.computed_styles_pool.get(node_id, {})

        # Emit DRAW_RECT for background color
        bg_color_str = styles.get("background-color", styles.get("background", ""))
        bg_color = parse_css_color(bg_color_str)
        if bg_color[3] > 0 and geom.width > 0 and geom.height > 0:
            display_list.add_command(DrawCommand(
                DrawCommandType.DRAW_RECT,
                geom.x, geom.y, geom.width, geom.height,
                color=bg_color
            ))

        # Emit DRAW_BORDER if border specified
        border_w_str = styles.get("border-width", styles.get("border", ""))
        border_c_str = styles.get("border-color", styles.get("color", "black"))
        if border_w_str and geom.width > 0 and geom.height > 0:
            b_w = float(border_w_str.replace("px", "").split()[0]) if border_w_str.replace("px", "").split()[0].isdigit() else 1.0
            b_color = parse_css_color(border_c_str)
            display_list.add_command(DrawCommand(
                DrawCommandType.DRAW_BORDER,
                geom.x, geom.y, geom.width, geom.height,
                color=b_color,
                border_width=b_w
            ))

        # Emit DRAW_TEXT if text payload exists
        text_payload = bank.text_pool.get(node_id, "")
        if text_payload:
            text_color = parse_css_color(styles.get("color", "black"))
            display_list.add_command(DrawCommand(
                DrawCommandType.DRAW_TEXT,
                geom.x, geom.y, geom.width, geom.height,
                color=text_color,
                text=text_payload
            ))

        # Traverse Children
        child_id = entity.first_child_index
        while child_id != 0xFFFFFFFF and child_id < bank.count:
            cls._traverse_and_emit(bank, child_id, display_list)
            child_id = bank.entities[child_id].next_sibling_index


class RGBABuffer:
    """Contiguous 32-bit RGBA Frame Buffer for software pixel rasterization."""
    def __init__(self, width: int = 1280, height: int = 800):
        self.width = width
        self.height = height
        self.data = bytearray(width * height * 4)
        self.clear()

    def clear(self, color: Tuple[int, int, int, int] = (255, 255, 255, 255)) -> None:
        """Clears frame buffer to specified background color."""
        r, g, b, a = color
        pixel_bytes = bytes([r, g, b, a])
        self.data[:] = pixel_bytes * (self.width * self.height)

    def set_pixel(self, x: int, y: int, r: int, g: int, b: int, a: int) -> None:
        """Sets a single pixel RGBA value with bounds checking."""
        if 0 <= x < self.width and 0 <= y < self.height:
            offset = (y * self.width + x) * 4
            self.data[offset] = r
            self.data[offset + 1] = g
            self.data[offset + 2] = b
            self.data[offset + 3] = a

    def fill_rect(self, rx: int, ry: int, rw: int, rh: int, r: int, g: int, b: int, a: int) -> None:
        """Fills a rectangular region with specified RGBA color."""
        x_min = max(0, rx)
        x_max = min(self.width, rx + rw)
        y_min = max(0, ry)
        y_max = min(self.height, ry + rh)

        if x_min >= x_max or y_min >= y_max:
            return

        span_width = x_max - x_min
        span_bytes = bytes([r, g, b, a]) * span_width

        for y in range(y_min, y_max):
            offset = (y * self.width + x_min) * 4
            self.data[offset:offset + len(span_bytes)] = span_bytes

    def draw_border(self, rx: int, ry: int, rw: int, rh: int, bw: int, r: int, g: int, b: int, a: int) -> None:
        """Draws a rectangular border outline."""
        # Top & Bottom borders
        self.fill_rect(rx, ry, rw, bw, r, g, b, a)
        self.fill_rect(rx, ry + rh - bw, rw, bw, r, g, b, a)

        # Left & Right borders
        self.fill_rect(rx, ry, bw, rh, r, g, b, a)
        self.fill_rect(rx + rw - bw, ry, bw, rh, r, g, b, a)


class SoftwareRasterizer:
    """Executes Display List draw commands sequentially into RGBABuffer."""

    @classmethod
    def rasterize(cls, display_list: DisplayList, target_buffer: RGBABuffer) -> int:
        cmds_processed = 0

        for cmd in display_list.commands:
            rx = int(round(cmd.x))
            ry = int(round(cmd.y))
            rw = int(round(cmd.width))
            rh = int(round(cmd.height))
            r, g, b, a = cmd.color

            if cmd.command_type == DrawCommandType.CLEAR_SCREEN:
                target_buffer.clear(cmd.color)
            elif cmd.command_type == DrawCommandType.DRAW_RECT:
                target_buffer.fill_rect(rx, ry, rw, rh, r, g, b, a)
            elif cmd.command_type == DrawCommandType.DRAW_BORDER:
                bw = int(max(1, round(cmd.border_width)))
                target_buffer.draw_border(rx, ry, rw, rh, bw, r, g, b, a)
            elif cmd.command_type == DrawCommandType.DRAW_TEXT:
                # Basic Software Glyph Box Representation
                target_buffer.fill_rect(rx, ry, rw, rh, r, g, b, a)

            cmds_processed += 1

        return cmds_processed
