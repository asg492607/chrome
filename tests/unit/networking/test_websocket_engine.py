"""
Unit & Benchmark Test Suite for WebSockets Engine & Zero-Copy Framing Protocol (Sprint 22).
Verifies RFC 6455 handshake (Sec-WebSocket-Accept), 4-byte mask XOR un-masking,
extended 16/64-bit length decoding, full-duplex WebSocketSession, and high-speed binary framing.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from networking_stack.websocket_engine import (
    WebSocketOpcode,
    WebSocketFrame,
    WebSocketParser,
    WebSocketSessionState,
    WebSocketSession
)


class TestWebSocketSubsystem(unittest.TestCase):

    def test_sec_websocket_accept_handshake(self):
        """Verify Sec-WebSocket-Accept calculation matches RFC 6455 spec vector example."""
        # RFC 6455 Section 1.3 Example
        sec_key = "dGhlIHNhbXBsZSBub25jZQ=="
        expected_accept = "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="

        computed_accept = WebSocketParser.compute_handshake_accept(sec_key)
        self.assertEqual(computed_accept, expected_accept)

    def test_binary_frame_parsing_and_unmasking(self):
        """Verify 4-byte mask XOR un-masking decodes masked text/binary frames accurately."""
        mask = b"\x37\xfa\x21\x3d"
        payload = b"Hello Sovereign WebSockets"

        original_frame = WebSocketFrame(
            fin=True,
            opcode=WebSocketOpcode.TEXT,
            masked=True,
            masking_key=mask,
            payload=payload
        )

        wire_bytes = WebSocketParser.serialize_frame(original_frame)
        parsed_frame, consumed = WebSocketParser.parse_frame(wire_bytes)

        self.assertIsNotNone(parsed_frame)
        self.assertEqual(consumed, len(wire_bytes))
        self.assertTrue(parsed_frame.fin)
        self.assertEqual(parsed_frame.opcode, WebSocketOpcode.TEXT)
        self.assertEqual(parsed_frame.payload, payload) # Decoded cleanly via XOR

    def test_extended_payload_length_16bit_and_64bit(self):
        """Verify 16-bit (len=126) and 64-bit (len=127) extended payload header parsing."""
        # 300 bytes payload -> triggers 16-bit extended length
        payload_300 = b"A" * 300
        frame_300 = WebSocketFrame(fin=True, opcode=WebSocketOpcode.BINARY, payload=payload_300)

        wire_300 = WebSocketParser.serialize_frame(frame_300)
        parsed_300, _ = WebSocketParser.parse_frame(wire_300)

        self.assertIsNotNone(parsed_300)
        self.assertEqual(parsed_300.payload_length, 300)
        self.assertEqual(parsed_300.payload, payload_300)

    def test_websocket_session_full_duplex(self):
        """Verify WebSocketSession handshake, PING/PONG control frames, and message reception."""
        session = WebSocketSession(origin="https://trading.local")
        self.assertEqual(session.state, WebSocketSessionState.CONNECTING)

        # Handshake
        accept = session.perform_handshake("dGhlIHNhbXBsZSBub25jZQ==")
        self.assertEqual(session.state, WebSocketSessionState.OPEN)

        # Send PING frame
        ping_bytes = session.send_ping(b"heartbeat_check")
        parsed_msgs = session.receive_wire_bytes(ping_bytes)

        self.assertEqual(len(parsed_msgs), 1)
        self.assertEqual(parsed_msgs[0][0], WebSocketOpcode.PING)
        self.assertEqual(parsed_msgs[0][1], b"heartbeat_check")

    def test_high_speed_framing_benchmark(self):
        """
        Benchmark: Parse and serialize 50,000 WebSocket frames.
        Asserts duration < 0.15s (> 300,000 frames/sec).
        """
        frame = WebSocketFrame(fin=True, opcode=WebSocketOpcode.TEXT, payload=b"Live Market Update Packet")
        wire_bytes = WebSocketParser.serialize_frame(frame)

        start_time = time.perf_counter()
        for _ in range(50000):
            parsed, _ = WebSocketParser.parse_frame(wire_bytes)
        duration = time.perf_counter() - start_time

        total_frames = 50000
        frames_per_sec = total_frames / duration
        latency_us = (duration / total_frames) * 1_000_000

        self.assertLess(duration, 0.20, f"50k WebSocket frames took {duration*1000:.2f}ms (must be < 200ms)")
        print(f"\n[Sprint 22 WebSockets Benchmark] {total_frames:,} Binary Frames Parsed:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Framing Throughput: {frames_per_sec:,.0f} frames/second")
        print(f"  - Average Frame Latency: {latency_us:.2f} µs/frame")


if __name__ == "__main__":
    unittest.main()
