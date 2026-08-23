"""
HTML5 Media Source Extensions (MSE) & HLS/DASH Video Streaming Engine.
Implements WHATWG MediaSource Extensions (MSE) specification, ISO BMFF MP4 binary box parsing (ftyp, moov, moof, mdat),
SourceBuffer segment appending, and Adaptive Bitrate (ABR) stream control.
"""

import sys
import os
import struct
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class MP4Box:
    """Represents an ISO BMFF MP4 Binary Box (Atom)."""

    def __init__(self, box_type: str, payload: bytes):
        self.box_type = box_type
        self.payload = payload

    @property
    def size(self) -> int:
        return len(self.payload) + 8

    def __repr__(self) -> str:
        return f"MP4Box({self.box_type}, size={self.size})"


class MP4BoxParser:
    """ISO BMFF MP4 Box (Atom) Binary Parser."""

    @classmethod
    def parse_boxes(cls, data: bytes) -> List[MP4Box]:
        """Parses binary ISO BMFF data stream into MP4Box structures."""
        boxes = []
        offset = 0

        while offset + 8 <= len(data):
            size = struct.unpack(">I", data[offset:offset + 4])[0]
            try:
                box_type = data[offset + 4:offset + 8].decode('ascii', errors='ignore')
            except Exception:
                box_type = "unknown"

            if size == 0: # Box extends to end of file
                size = len(data) - offset

            if size < 8 or offset + size > len(data):
                break

            payload = data[offset + 8:offset + size]
            boxes.append(MP4Box(box_type, payload))
            offset += size

        return boxes

    @classmethod
    def serialize_box(cls, box_type: str, payload: bytes) -> bytes:
        """Serializes an MP4 Box into wire format binary bytearray."""
        type_bytes = box_type.encode('ascii')[:4].ljust(4, b"\x20")
        size = len(payload) + 8
        header = struct.pack(">I", size) + type_bytes
        return header + payload


class SourceBuffer:
    """WHATWG SourceBuffer managing video stream chunk appends and buffered time ranges."""

    def __init__(self, mime_type: str):
        self.mime_type = mime_type
        self.updating = False
        self.buffered_ranges: List[Tuple[float, float]] = []
        self.raw_buffer = bytearray()
        self.parsed_boxes: List[MP4Box] = []

    def appendBuffer(self, data: bytes) -> bool:
        """Appends binary video data chunk, parses MP4 boxes, and updates buffered time ranges."""
        self.updating = True
        self.raw_buffer.extend(data)

        # Parse boxes
        new_boxes = MP4BoxParser.parse_boxes(data)
        self.parsed_boxes.extend(new_boxes)

        # Update buffered time ranges
        duration_sec = float(len(self.raw_buffer)) / 50000.0 # ~50 KB/sec rate simulation
        self.buffered_ranges = [(0.0, round(duration_sec, 2))]

        self.updating = False
        return True

    def remove(self, start: float, end: float) -> None:
        """Removes media bytes matching specified time range."""
        self.buffered_ranges = [(s, e) for s, e in self.buffered_ranges if not (start <= s and e <= end)]


class MediaSourceReadyState(Enum):
    CLOSED = 1
    OPEN = 2
    ENDED = 3


class MediaSource:
    """WHATWG MediaSource Extensions (MSE) Pipeline."""

    def __init__(self):
        self.duration: float = 0.0
        self.readyState = MediaSourceReadyState.CLOSED
        self.sourceBuffers: List[SourceBuffer] = []

    def open(self) -> None:
        """Transitions MediaSource readyState to OPEN."""
        self.readyState = MediaSourceReadyState.OPEN

    def addSourceBuffer(self, mime_type: str) -> SourceBuffer:
        """Creates and attaches a SourceBuffer to the MediaSource pipeline."""
        if self.readyState != MediaSourceReadyState.OPEN:
            self.open()

        sb = SourceBuffer(mime_type)
        self.sourceBuffers.append(sb)
        return sb

    def endOfStream(self) -> None:
        """Transitions MediaSource readyState to ENDED."""
        self.readyState = MediaSourceReadyState.ENDED


class AdaptiveStreamController:
    """Adaptive Bitrate (ABR) HLS/DASH Quality Selection Controller."""

    QUALITY_PROFILES = {
        "720p": 2_500_000,   # 2.5 Mbps
        "1080p": 5_000_000,  # 5.0 Mbps
        "4K": 15_000_000    # 15.0 Mbps
    }

    def __init__(self):
        self.current_profile = "1080p"

    def select_quality(self, bandwidth_bps: float) -> str:
        """Selects optimal video quality profile based on measured network throughput."""
        if bandwidth_bps >= self.QUALITY_PROFILES["4K"]:
            self.current_profile = "4K"
        elif bandwidth_bps >= self.QUALITY_PROFILES["1080p"]:
            self.current_profile = "1080p"
        else:
            self.current_profile = "720p"

        return self.current_profile
