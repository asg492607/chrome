"""
WebSockets Engine & Zero-Copy Framing Protocol.
Implements RFC 6455 binary frame parsing, Sec-WebSocket-Accept SHA-1/Base64 handshake,
4-byte mask XOR un-masking (P_i = C_i ^ M_{i mod 4}), extended 16/64-bit length decoding, and full-duplex WebSocketSession.
"""

import sys
import os
import struct
import hashlib
import base64
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class WebSocketOpcode(Enum):
    CONTINUATION = 0x0
    TEXT = 0x1
    BINARY = 0x2
    CLOSE = 0x8
    PING = 0x9
    PONG = 0xA


class WebSocketFrame:
    """Represents an RFC 6455 WebSocket Binary Frame."""

    def __init__(
        self,
        fin: bool = True,
        opcode: WebSocketOpcode = WebSocketOpcode.TEXT,
        masked: bool = False,
        masking_key: Optional[bytes] = None,
        payload: bytes = b""
    ):
        self.fin = fin
        self.opcode = opcode
        self.masked = masked
        self.masking_key = masking_key
        self.payload = payload

    @property
    def payload_length(self) -> int:
        return len(self.payload)

    def __repr__(self) -> str:
        return f"WSFrame(fin={self.fin}, opcode={self.opcode.name}, masked={self.masked}, payload_len={self.payload_length})"


class WebSocketParser:
    """RFC 6455 Handshake, Frame Parser, and Mask XOR Encoder/Decoder."""

    WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

    @classmethod
    def compute_handshake_accept(cls, sec_websocket_key: str) -> str:
        """Calculates Sec-WebSocket-Accept SHA-1/Base64 response hash according to RFC 6455 section 4.2.2."""
        combined = sec_websocket_key.strip() + cls.WS_GUID
        sha1_digest = hashlib.sha1(combined.encode('utf-8')).digest()
        return base64.b64encode(sha1_digest).decode('utf-8')

    @classmethod
    def unmask_payload(cls, payload: bytes, masking_key: Optional[bytes]) -> bytes:
        """Performs 4-byte mask XOR un-masking: P_i = C_i ^ M_{i mod 4}."""
        if not masking_key or len(masking_key) != 4 or not payload:
            return payload
        return bytes([b ^ masking_key[i % 4] for i, b in enumerate(payload)])

    @classmethod
    def parse_frame(cls, data: bytes) -> Tuple[Optional[WebSocketFrame], int]:
        """
        Parses wire-format raw bytes into a WebSocketFrame.
        Returns (frame, total_bytes_consumed). If incomplete, returns (None, 0).
        """
        if len(data) < 2:
            return None, 0

        b0 = data[0]
        b1 = data[1]

        fin = (b0 & 0x80) != 0
        opcode_val = b0 & 0x0F

        try:
            opcode = WebSocketOpcode(opcode_val)
        except ValueError:
            return None, 0

        masked = (b1 & 0x80) != 0
        payload_len_val = b1 & 0x7F

        offset = 2

        # 16-bit extended length
        if payload_len_val == 126:
            if len(data) < offset + 2:
                return None, 0
            payload_len = struct.unpack("!H", data[offset:offset + 2])[0]
            offset += 2

        # 64-bit extended length
        elif payload_len_val == 127:
            if len(data) < offset + 8:
                return None, 0
            payload_len = struct.unpack("!Q", data[offset:offset + 8])[0]
            offset += 8

        else:
            payload_len = payload_len_val

        # Masking key (4 bytes)
        masking_key = None
        if masked:
            if len(data) < offset + 4:
                return None, 0
            masking_key = data[offset:offset + 4]
            offset += 4

        # Payload bytes check
        if len(data) < offset + payload_len:
            return None, 0

        raw_payload = data[offset:offset + payload_len]
        decoded_payload = cls.unmask_payload(raw_payload, masking_key) if masked else raw_payload

        frame = WebSocketFrame(
            fin=fin,
            opcode=opcode,
            masked=masked,
            masking_key=masking_key,
            payload=decoded_payload
        )

        return frame, offset + payload_len

    @classmethod
    def serialize_frame(cls, frame: WebSocketFrame) -> bytes:
        """Serializes a WebSocketFrame into wire-format binary byte stream."""
        b0 = (0x80 if frame.fin else 0x00) | (frame.opcode.value & 0x0F)

        p_len = len(frame.payload)
        mask_bit = 0x80 if frame.masked else 0x00

        header = bytearray()

        if p_len < 126:
            header.append(b0)
            header.append(mask_bit | p_len)
        elif p_len <= 0xFFFF:
            header.append(b0)
            header.append(mask_bit | 126)
            header.extend(struct.pack("!H", p_len))
        else:
            header.append(b0)
            header.append(mask_bit | 127)
            header.extend(struct.pack("!Q", p_len))

        if frame.masked and frame.masking_key:
            header.extend(frame.masking_key)
            masked_payload = cls.unmask_payload(frame.payload, frame.masking_key)
            return bytes(header) + masked_payload

        return bytes(header) + frame.payload


class WebSocketSessionState(Enum):
    CONNECTING = 1
    OPEN = 2
    CLOSING = 3
    CLOSED = 4


class WebSocketSession:
    """Full-duplex WebSocket Session handling text/binary messages and ping-pong control frames."""

    def __init__(self, origin: str, socket_id: int = 1):
        self.origin = origin
        self.socket_id = socket_id
        self.state = WebSocketSessionState.CONNECTING

        self.received_messages: List[Tuple[WebSocketOpcode, bytes]] = []

    def perform_handshake(self, sec_key: str) -> str:
        """Completes RFC 6455 handshake and transitions state to OPEN."""
        accept_hash = WebSocketParser.compute_handshake_accept(sec_key)
        self.state = WebSocketSessionState.OPEN
        return accept_hash

    def send_text(self, text: str) -> bytes:
        """Encodes text payload into a WebSocket TEXT frame."""
        frame = WebSocketFrame(fin=True, opcode=WebSocketOpcode.TEXT, payload=text.encode('utf-8'))
        return WebSocketParser.serialize_frame(frame)

    def send_binary(self, data: bytes) -> bytes:
        """Encodes binary payload into a WebSocket BINARY frame."""
        frame = WebSocketFrame(fin=True, opcode=WebSocketOpcode.BINARY, payload=data)
        return WebSocketParser.serialize_frame(frame)

    def send_ping(self, data: bytes = b"ping") -> bytes:
        """Encodes PING control frame."""
        frame = WebSocketFrame(fin=True, opcode=WebSocketOpcode.PING, payload=data)
        return WebSocketParser.serialize_frame(frame)

    def send_pong(self, data: bytes = b"pong") -> bytes:
        """Encodes PONG control frame."""
        frame = WebSocketFrame(fin=True, opcode=WebSocketOpcode.PONG, payload=data)
        return WebSocketParser.serialize_frame(frame)

    def receive_wire_bytes(self, raw_bytes: bytes) -> List[Tuple[WebSocketOpcode, bytes]]:
        """Parses incoming wire bytes and extracts opcode/payload messages."""
        consumed = 0
        frames_parsed = []

        while consumed < len(raw_bytes):
            frame, len_read = WebSocketParser.parse_frame(raw_bytes[consumed:])
            if len_read == 0 or frame is None:
                break
            consumed += len_read

            if frame.opcode == WebSocketOpcode.CLOSE:
                self.state = WebSocketSessionState.CLOSED
            elif frame.opcode in (WebSocketOpcode.TEXT, WebSocketOpcode.BINARY, WebSocketOpcode.PING, WebSocketOpcode.PONG):
                self.received_messages.append((frame.opcode, frame.payload))
                frames_parsed.append((frame.opcode, frame.payload))

        return frames_parsed
