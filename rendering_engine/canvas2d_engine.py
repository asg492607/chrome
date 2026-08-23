"""
HTML5 Canvas 2D Vector Rendering Context Engine.
Implements WHATWG Canvas 2D state machine (save/restore), 2D affine matrix transformations,
Path2D vector drawing commands, and software RGBA pixel rasterization.
"""

import sys
import os
import math
import struct
from typing import Dict, List, Optional, Tuple, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class Canvas2DState:
    """Represents a snapshot of Canvas 2D context style state and transform matrix."""

    def __init__(self):
        self.fill_style: str = "#000000"
        self.stroke_style: str = "#000000"
        self.line_width: float = 1.0
        self.global_alpha: float = 1.0
        # 2D Affine Transformation Matrix [a, b, c, d, e, f]
        self.matrix: List[float] = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]

    def copy(self) -> "Canvas2DState":
        """Creates a deep copy of the state for stack operations."""
        st = Canvas2DState()
        st.fill_style = self.fill_style
        st.stroke_style = self.stroke_style
        st.line_width = self.line_width
        st.global_alpha = self.global_alpha
        st.matrix = list(self.matrix)
        return st


class PathCommand:
    """Represents a vector path command instruction."""

    def __init__(self, cmd: str, params: List[float]):
        self.cmd = cmd
        self.params = params

    def __repr__(self) -> str:
        return f"PathCmd({self.cmd}, {self.params})"


class Path2D:
    """WHATWG Path2D Vector Path Pipeline."""

    def __init__(self):
        self.commands: List[PathCommand] = []

    def moveTo(self, x: float, y: float) -> None:
        self.commands.append(PathCommand("MOVE_TO", [x, y]))

    def lineTo(self, x: float, y: float) -> None:
        self.commands.append(PathCommand("LINE_TO", [x, y]))

    def rect(self, x: float, y: float, width: float, height: float) -> None:
        self.commands.append(PathCommand("RECT", [x, y, width, height]))

    def arc(self, x: float, y: float, radius: float, start_angle: float, end_angle: float) -> None:
        self.commands.append(PathCommand("ARC", [x, y, radius, start_angle, end_angle]))

    def closePath(self) -> None:
        self.commands.append(PathCommand("CLOSE", []))


class CanvasRenderingContext2D:
    """WHATWG Canvas 2D Rendering Context Engine."""

    def __init__(self, width: int = 800, height: int = 600):
        self.width = width
        self.height = height
        # Contiguous 32-bit RGBA pixel bytearray
        self.pixel_buffer = bytearray(width * height * 4)
        self.state = Canvas2DState()
        self.state_stack: List[Canvas2DState] = []
        self.current_path = Path2D()

    # --- State Management ---
    def save(self) -> None:
        """Pushes current context state onto the state stack."""
        self.state_stack.append(self.state.copy())

    def restore(self) -> None:
        """Pops and restores the previous context state from the stack."""
        if self.state_stack:
            self.state = self.state_stack.pop()

    # --- Transformations ---
    def translate(self, tx: float, ty: float) -> None:
        """Applies translation to current matrix."""
        self.state.matrix[4] += tx
        self.state.matrix[5] += ty

    def scale(self, sx: float, sy: float) -> None:
        """Applies scaling to current matrix."""
        self.state.matrix[0] *= sx
        self.state.matrix[3] *= sy

    def rotate(self, angle_rad: float) -> None:
        """Applies rotation to current matrix."""
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        a, b, c, d = self.state.matrix[0], self.state.matrix[1], self.state.matrix[2], self.state.matrix[3]
        self.state.matrix[0] = a * cos_a + c * sin_a
        self.state.matrix[1] = b * cos_a + d * sin_a
        self.state.matrix[2] = a * -sin_a + c * cos_a
        self.state.matrix[3] = b * -sin_a + d * cos_a

    def transform(self, a: float, b: float, c: float, d: float, e: float, f: float) -> None:
        """Sets explicit 2D affine transform matrix."""
        self.state.matrix = [a, b, c, d, e, f]

    # --- Path Drawing API ---
    def beginPath(self) -> None:
        """Resets active path vector."""
        self.current_path = Path2D()

    def moveTo(self, x: float, y: float) -> None:
        self.current_path.moveTo(x, y)

    def lineTo(self, x: float, y: float) -> None:
        self.current_path.lineTo(x, y)

    def rect(self, x: float, y: float, width: float, height: float) -> None:
        self.current_path.rect(x, y, width, height)

    def arc(self, x: float, y: float, radius: float, start_angle: float, end_angle: float) -> None:
        self.current_path.arc(x, y, radius, start_angle, end_angle)

    def closePath(self) -> None:
        self.current_path.closePath()

    # --- Rasterization Methods ---
    def fillRect(self, x: float, y: float, width: float, height: float) -> None:
        """Fills a transformed rectangle into the pixel buffer."""
        # Apply matrix translation
        tx = x + self.state.matrix[4]
        ty = y + self.state.matrix[5]
        tw = width * self.state.matrix[0]
        th = height * self.state.matrix[3]

        r, g, b, a = self._parse_color(self.state.fill_style, self.state.global_alpha)

        start_x = max(0, int(tx))
        end_x = min(self.width, int(tx + tw))
        start_y = max(0, int(ty))
        end_y = min(self.height, int(ty + th))

        for py in range(start_y, end_y):
            row_start = (py * self.width + start_x) * 4
            row_end = (py * self.width + end_x) * 4
            pixel = bytes([r, g, b, a])
            self.pixel_buffer[row_start:row_end] = pixel * (end_x - start_x)

    def strokeRect(self, x: float, y: float, width: float, height: float) -> None:
        """Strokes a rectangle border into the pixel buffer."""
        lw = int(self.state.line_width)
        # Top border
        self.fillRect(x, y, width, lw)
        # Bottom border
        self.fillRect(x, y + height - lw, width, lw)
        # Left border
        self.fillRect(x, y, lw, height)
        # Right border
        self.fillRect(x + width - lw, y, lw, height)

    def clearRect(self, x: float, y: float, width: float, height: float) -> None:
        """Clears pixel rectangle to transparent RGBA zero."""
        start_x = max(0, int(x))
        end_x = min(self.width, int(x + width))
        start_y = max(0, int(y))
        end_y = min(self.height, int(y + height))

        zero_pixel = b"\x00\x00\x00\x00"
        for py in range(start_y, end_y):
            row_start = (py * self.width + start_x) * 4
            row_end = (py * self.width + end_x) * 4
            self.pixel_buffer[row_start:row_end] = zero_pixel * (end_x - start_x)

    def fill(self) -> None:
        """Fills active vector path."""
        for cmd in self.current_path.commands:
            if cmd.cmd == "RECT":
                x, y, w, h = cmd.params
                self.fillRect(x, y, w, h)

    def stroke(self) -> None:
        """Strokes active vector path outline."""
        for cmd in self.current_path.commands:
            if cmd.cmd == "RECT":
                x, y, w, h = cmd.params
                self.strokeRect(x, y, w, h)

    # --- ImageData API ---
    def getImageData(self, x: int, y: int, width: int, height: int) -> bytearray:
        """Extracts pixel bytearray slice."""
        result = bytearray(width * height * 4)
        for py in range(height):
            src_start = ((y + py) * self.width + x) * 4
            src_end = src_start + (width * 4)
            dst_start = (py * width) * 4
            dst_end = dst_start + (width * 4)
            if src_end <= len(self.pixel_buffer):
                result[dst_start:dst_end] = self.pixel_buffer[src_start:src_end]
        return result

    def putImageData(self, image_data: bytearray, x: int, y: int, width: int, height: int) -> None:
        """Writes ImageData bytearray slice into buffer."""
        for py in range(height):
            dst_start = ((y + py) * self.width + x) * 4
            dst_end = dst_start + (width * 4)
            src_start = (py * width) * 4
            src_end = src_start + (width * 4)
            if dst_end <= len(self.pixel_buffer) and src_end <= len(image_data):
                self.pixel_buffer[dst_start:dst_end] = image_data[src_start:src_end]

    def _parse_color(self, color_str: str, alpha: float) -> Tuple[int, int, int, int]:
        """Parses hex or named color strings into RGBA tuple."""
        r, g, b = 0, 0, 0
        if color_str.startswith("#"):
            hex_val = color_str.lstrip("#")
            if len(hex_val) == 6:
                r = int(hex_val[0:2], 16)
                g = int(hex_val[2:4], 16)
                b = int(hex_val[4:6], 16)
        elif color_str == "red":
            r = 255
        elif color_str == "green":
            g = 255
        elif color_str == "blue":
            b = 255

        a = int(alpha * 255)
        return (r, g, b, a)
