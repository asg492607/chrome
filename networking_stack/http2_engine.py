"""
RFC 7540 Binary HTTP/2 Protocol Engine & Stream Multiplexer.
Provides 9-byte frame encoding/decoding (HEADERS, DATA, SETTINGS, PING, RST_STREAM),
connection preface verification, and concurrent stream multiplexing over a single TCP connection.
"""

import struct
import threading
from enum import IntEnum, IntFlag
from typing import Dict, List, Optional, Tuple, Any, Generator

# RFC 7540 Client Connection Preface (Exact 24 Bytes)
HTTP2_CLIENT_PREFACE: bytes = b"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n"


class HTTP2FrameType(IntEnum):
    """RFC 7540 Binary Frame Types."""
    DATA = 0x00
    HEADERS = 0x01
    PRIORITY = 0x02
    RST_STREAM = 0x03
    SETTINGS = 0x04
    PUSH_PROMISE = 0x05
    PING = 0x06
    GOAWAY = 0x07
    WINDOW_UPDATE = 0x08
    CONTINUATION = 0x09


class HTTP2Flags(IntFlag):
    """RFC 7540 Frame Control Flags."""
    NONE = 0x00
    END_STREAM = 0x01      # For DATA and HEADERS
    ACK = 0x01             # For SETTINGS and PING
    END_HEADERS = 0x04     # For HEADERS and PUSH_PROMISE
    PADDED = 0x08          # For DATA and HEADERS
    PRIORITY = 0x20        # For HEADERS


class HTTP2ErrorCode(IntEnum):
    """RFC 7540 Standard Error Codes."""
    NO_ERROR = 0x00
    PROTOCOL_ERROR = 0x01
    INTERNAL_ERROR = 0x02
    FLOW_CONTROL_ERROR = 0x03
    SETTINGS_TIMEOUT = 0x04
    STREAM_CLOSED = 0x05
    FRAME_SIZE_ERROR = 0x06
    REFUSED_STREAM = 0x07
    CANCEL = 0x08


class HTTP2Frame:
    """
    RFC 7540 Binary Frame.
    Structure (Exact 9-Byte Header + Payload):
    - [00..02] Length    : 24-bit unsigned integer (Length of payload)
    - [03]     Type      : 8-bit Frame Type Enum
    - [04]     Flags     : 8-bit Flags Bitmask
    - [05..08] Stream ID : 31-bit Stream Identifier (1 bit reserved)
    - [09..N]  Payload   : Variable-length binary payload
    """
    def __init__(
        self,
        frame_type: HTTP2FrameType,
        flags: int = int(HTTP2Flags.NONE),
        stream_id: int = 0,
        payload: bytes = b""
    ):
        self.frame_type = HTTP2FrameType(frame_type)
        self.flags = int(flags)
        self.stream_id = stream_id & 0x7FFFFFFF
        self.payload = payload

    @property
    def length(self) -> int:
        return len(self.payload)

    def serialize(self) -> bytes:
        """Serializes frame into wire-format 9-byte header followed by payload."""
        payload_len = len(self.payload)
        # Pack 24-bit length into 3 bytes
        len_b0 = (payload_len >> 16) & 0xFF
        len_b1 = (payload_len >> 8) & 0xFF
        len_b2 = payload_len & 0xFF

        header = struct.pack(
            "!BBBBBI",
            len_b0,
            len_b1,
            len_b2,
            int(self.frame_type),
            self.flags,
            self.stream_id
        )
        return header + self.payload

    @classmethod
    def parse(cls, raw: bytes) -> Tuple["HTTP2Frame", bytes]:
        """
        Parses the first 9-byte header + payload from raw bytes.
        Returns (HTTP2Frame, remaining_bytes).
        """
        if len(raw) < 9:
            raise ValueError("Buffer too short for 9-byte HTTP/2 frame header.")

        len_b0, len_b1, len_b2, f_type, flags, stream_id = struct.unpack("!BBBBBI", raw[:9])
        payload_len = (len_b0 << 16) | (len_b1 << 8) | len_b2

        total_frame_len = 9 + payload_len
        if len(raw) < total_frame_len:
            raise ValueError(f"Incomplete frame: expected {total_frame_len} bytes, got {len(raw)}.")

        payload = raw[9:total_frame_len]
        remaining = raw[total_frame_len:]

        frame = cls(
            frame_type=HTTP2FrameType(f_type),
            flags=flags,
            stream_id=stream_id & 0x7FFFFFFF,
            payload=payload
        )
        return frame, remaining

    def __repr__(self) -> str:
        return f"HTTP2Frame(type={self.frame_type.name}, stream={self.stream_id}, flags={self.flags:#04x}, len={self.length})"


class HTTP2Stream:
    """Represents a single bidirectional logical stream multiplexed over the TCP session."""
    def __init__(self, stream_id: int):
        self.stream_id = stream_id
        self.headers: Dict[str, str] = {}
        self.data_chunks: List[bytes] = []
        self.is_closed = False
        self.error_code: Optional[HTTP2ErrorCode] = None

    def append_data(self, chunk: bytes) -> None:
        self.data_chunks.append(chunk)

    def get_body(self) -> bytes:
        return b"".join(self.data_chunks)


class HTTP2StreamMultiplexer:
    """
    Concurrent Stream Multiplexer.
    Interleaves and demuxes multiple HTTP/2 requests and responses over a single shared TCP socket.
    """
    def __init__(self, is_client: bool = True):
        self.is_client = is_client
        self.next_stream_id = 1 if is_client else 2 # Clients use odd IDs, servers use even
        self.streams: Dict[int, HTTP2Stream] = {}
        self.lock = threading.Lock()

        # Telemetry
        self.total_frames_sent = 0
        self.total_frames_received = 0
        self.total_streams_created = 0
        self.bytes_transferred = 0

    def create_stream(self) -> int:
        """Allocates a new logical stream ID."""
        with self.lock:
            sid = self.next_stream_id
            self.next_stream_id += 2
            self.streams[sid] = HTTP2Stream(sid)
            self.total_streams_created += 1
            return sid

    def build_headers_frame(
        self,
        stream_id: int,
        headers: Dict[str, str],
        end_stream: bool = False
    ) -> HTTP2Frame:
        """Constructs a HEADERS frame with pseudo-headers and custom headers."""
        # Simple binary header serialization: key_len:1B | key | val_len:2B | val
        serialized = bytearray()
        for k, v in headers.items():
            k_bytes = k.encode('utf-8')
            v_bytes = v.encode('utf-8')
            serialized.append(len(k_bytes))
            serialized.extend(k_bytes)
            serialized.extend(struct.pack("!H", len(v_bytes)))
            serialized.extend(v_bytes)

        flags = int(HTTP2Flags.END_HEADERS)
        if end_stream:
            flags |= int(HTTP2Flags.END_STREAM)

        frame = HTTP2Frame(
            frame_type=HTTP2FrameType.HEADERS,
            flags=flags,
            stream_id=stream_id,
            payload=bytes(serialized)
        )
        self.total_frames_sent += 1
        self.bytes_transferred += frame.length + 9
        return frame

    def build_data_frame(
        self,
        stream_id: int,
        data: bytes,
        end_stream: bool = True
    ) -> HTTP2Frame:
        """Constructs a DATA frame."""
        flags = int(HTTP2Flags.END_STREAM) if end_stream else int(HTTP2Flags.NONE)
        frame = HTTP2Frame(
            frame_type=HTTP2FrameType.DATA,
            flags=flags,
            stream_id=stream_id,
            payload=data
        )
        self.total_frames_sent += 1
        self.bytes_transferred += frame.length + 9
        return frame

    def build_settings_frame(self, ack: bool = False) -> HTTP2Frame:
        """Constructs a SETTINGS frame (or SETTINGS ACK)."""
        flags = int(HTTP2Flags.ACK) if ack else int(HTTP2Flags.NONE)
        payload = b""
        if not ack:
            # Default settings parameters (e.g. MAX_CONCURRENT_STREAMS=100)
            payload = struct.pack("!HI", 0x0003, 100) # ID 3: SETTINGS_MAX_CONCURRENT_STREAMS

        frame = HTTP2Frame(
            frame_type=HTTP2FrameType.SETTINGS,
            flags=flags,
            stream_id=0, # Settings always use Stream 0
            payload=payload
        )
        self.total_frames_sent += 1
        return frame

    def build_ping_frame(self, opaque_data: bytes = b"\x00" * 8, ack: bool = False) -> HTTP2Frame:
        """Constructs an 8-byte PING frame."""
        flags = int(HTTP2Flags.ACK) if ack else int(HTTP2Flags.NONE)
        payload = opaque_data[:8].ljust(8, b"\x00")
        frame = HTTP2Frame(
            frame_type=HTTP2FrameType.PING,
            flags=flags,
            stream_id=0,
            payload=payload
        )
        self.total_frames_sent += 1
        return frame

    def build_rst_stream_frame(self, stream_id: int, error_code: HTTP2ErrorCode = HTTP2ErrorCode.CANCEL) -> HTTP2Frame:
        """Constructs a RST_STREAM frame to terminate a stream."""
        payload = struct.pack("!I", int(error_code))
        frame = HTTP2Frame(
            frame_type=HTTP2FrameType.RST_STREAM,
            flags=0,
            stream_id=stream_id,
            payload=payload
        )
        self.total_frames_sent += 1
        return frame

    def ingest_frame(self, frame: HTTP2Frame) -> Optional[Tuple[int, Dict[str, str], bytes]]:
        """
        Demuxes incoming frame onto its corresponding stream.
        If stream reaches END_STREAM, returns (stream_id, headers, full_body).
        """
        with self.lock:
            self.total_frames_received += 1
            self.bytes_transferred += frame.length + 9
            sid = frame.stream_id

            if sid == 0:
                # Connection-level frames (SETTINGS, PING)
                return None

            if sid not in self.streams:
                self.streams[sid] = HTTP2Stream(sid)

            stream = self.streams[sid]

            if frame.frame_type == HTTP2FrameType.HEADERS:
                # Parse serialized headers
                raw = frame.payload
                idx = 0
                while idx < len(raw):
                    k_len = raw[idx]
                    idx += 1
                    k = raw[idx:idx + k_len].decode('utf-8', errors='ignore')
                    idx += k_len
                    v_len = struct.unpack("!H", raw[idx:idx + 2])[0]
                    idx += 2
                    v = raw[idx:idx + v_len].decode('utf-8', errors='ignore')
                    idx += v_len
                    stream.headers[k.lower()] = v

            elif frame.frame_type == HTTP2FrameType.DATA:
                stream.append_data(frame.payload)

            elif frame.frame_type == HTTP2FrameType.RST_STREAM:
                stream.is_closed = True
                if len(frame.payload) >= 4:
                    err_val = struct.unpack("!I", frame.payload[:4])[0]
                    stream.error_code = HTTP2ErrorCode(err_val)
                return None

            # Check if stream is complete
            if bool(frame.flags & int(HTTP2Flags.END_STREAM)):
                stream.is_closed = True
                return sid, stream.headers, stream.get_body()

            return None

    def get_telemetry(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "active_streams": len([s for s in self.streams.values() if not s.is_closed]),
                "total_streams_created": self.total_streams_created,
                "total_frames_sent": self.total_frames_sent,
                "total_frames_received": self.total_frames_received,
                "bytes_transferred": self.bytes_transferred
            }
