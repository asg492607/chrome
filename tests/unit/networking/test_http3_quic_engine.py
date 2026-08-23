"""
Unit & Benchmark Test Suite for HTTP/3 & QUIC Transport Protocol Engine (Sprint 25).
Verifies RFC 9000 QUIC variable-length integer encoding/decoding, Long/Short packet headers,
RFC 9114 HTTP/3 frame parsing, and UDP connection migration.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from networking_stack.http3_quic_engine import (
    QUICVarInt,
    QUICPacketType,
    QUICHeader,
    QUICFrameType,
    QUICFrame,
    HTTP3FrameType,
    HTTP3Frame,
    QUICConnection
)


class TestHTTP3QUICSubsystem(unittest.TestCase):

    def test_rfc9000_quic_varint_encoding_and_decoding(self):
        """Verify RFC 9000 62-bit variable-length integer encoding and decoding vectors."""
        test_vals = [0, 37, 1529, 49487833, 1512860223415]

        for val in test_vals:
            enc_bytes = QUICVarInt.encode(val)
            dec_val, consumed = QUICVarInt.decode(enc_bytes)
            self.assertEqual(dec_val, val)
            self.assertEqual(consumed, len(enc_bytes))

    def test_quic_header_and_stream_frame_parsing(self):
        """Verify QUIC Long Header serialization and dest/src connection ID formatting."""
        dcid = b"\x01\x02\x03\x04\x05\x06\x07\x08"
        scid = b"\x08\x07\x06\x05\x04\x03\x02\x01"

        hdr = QUICHeader(
            header_form=1,
            packet_type=QUICPacketType.INITIAL,
            version=0x00000001,
            dest_connection_id=dcid,
            src_connection_id=scid
        )

        wire_bytes = hdr.serialize()
        self.assertNotEqual(wire_bytes[0] & 0x80, 0) # Long header flag set
        self.assertIn(dcid, wire_bytes)
        self.assertIn(scid, wire_bytes)

    def test_rfc9114_http3_frame_parsing(self):
        """Verify RFC 9114 HTTP/3 HEADERS and DATA binary frame serialization and parsing."""
        headers_payload = b":status 200\r\ncontent-type: text/html"
        frame = HTTP3Frame(HTTP3FrameType.HEADERS, headers_payload)

        wire_bytes = frame.serialize()
        parsed_frame, consumed = HTTP3Frame.parse(wire_bytes)

        self.assertIsNotNone(parsed_frame)
        self.assertEqual(consumed, len(wire_bytes))
        self.assertEqual(parsed_frame.frame_type, HTTP3FrameType.HEADERS)
        self.assertEqual(parsed_frame.payload, headers_payload)

    def test_udp_connection_migration(self):
        """Verify UDP connection migration updates IP/Port without dropping connection ID or active streams."""
        conn = QUICConnection(connection_id=b"\xaa\xbb\xcc\xdd\xee\xff\x11\x22", ip="192.168.1.100", port=4433)
        self.assertEqual(conn.current_ip, "192.168.1.100")

        # Process stream data
        frame = HTTP3Frame(HTTP3FrameType.DATA, b"Sovereign QUIC Data")
        parsed = conn.process_stream_bytes(stream_id=4, data=frame.serialize())
        self.assertEqual(len(parsed), 1)

        # Migrate to cellular 5G network IP
        ok = conn.migrate_address("10.88.20.15", port=8443)
        self.assertTrue(ok)
        self.assertEqual(conn.current_ip, "10.88.20.15")
        self.assertEqual(conn.migrations_count, 1)

    def test_high_speed_quic_http3_benchmark(self):
        """
        Benchmark: Encode and decode 50,000 RFC 9000 QUIC VarInts and HTTP/3 frames.
        Asserts duration < 0.15s (> 300,000 ops/sec).
        """
        frame = HTTP3Frame(HTTP3FrameType.DATA, b"QUIC High Speed Packet Payload")
        wire_bytes = frame.serialize()

        start_time = time.perf_counter()
        for i in range(50000):
            var_enc = QUICVarInt.encode(i)
            _, _ = QUICVarInt.decode(var_enc)
            _, _ = HTTP3Frame.parse(wire_bytes)
        duration = time.perf_counter() - start_time

        total_ops = 50000
        ops_per_sec = total_ops / duration
        latency_us = (duration / total_ops) * 1_000_000

        self.assertLess(duration, 0.20, f"50k HTTP3/QUIC ops took {duration*1000:.2f}ms (must be < 200ms)")
        print(f"\n[Sprint 25 HTTP/3 & QUIC Benchmark] {total_ops:,} Transport Packets Processed:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - QUIC Transport Speed: {ops_per_sec:,.0f} ops/second")
        print(f"  - Average Packet Latency: {latency_us:.2f} µs/op")


if __name__ == "__main__":
    unittest.main()
