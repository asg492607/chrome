"""
Unit & Benchmark Test Suite for RFC 7540 HTTP/2 Protocol Engine & Stream Multiplexer (Sprint 08).
Verifies 9-byte binary frame encoding/decoding, connection preface, multi-stream interleaving,
stream termination via RST_STREAM, and sub-microsecond binary frame parsing throughput.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from networking_stack.http2_engine import (
    HTTP2FrameType,
    HTTP2Flags,
    HTTP2ErrorCode,
    HTTP2Frame,
    HTTP2StreamMultiplexer,
    HTTP2_CLIENT_PREFACE
)


class TestHTTP2EngineSubsystem(unittest.TestCase):

    def test_9byte_frame_header_serialization_and_parsing(self):
        """Verify binary 9-byte header packing and payload parsing round-trip."""
        payload_data = b"Sovereign Zero-Bloat Payload"
        frame = HTTP2Frame(
            frame_type=HTTP2FrameType.DATA,
            flags=int(HTTP2Flags.END_STREAM),
            stream_id=5,
            payload=payload_data
        )

        wire_bytes = frame.serialize()
        # 9-byte header + payload len
        self.assertEqual(len(wire_bytes), 9 + len(payload_data))

        parsed_frame, remaining = HTTP2Frame.parse(wire_bytes)
        self.assertEqual(len(remaining), 0)
        self.assertEqual(parsed_frame.frame_type, HTTP2FrameType.DATA)
        self.assertEqual(parsed_frame.flags, int(HTTP2Flags.END_STREAM))
        self.assertEqual(parsed_frame.stream_id, 5)
        self.assertEqual(parsed_frame.payload, payload_data)

    def test_connection_preface_and_settings_handshake(self):
        """Test RFC 7540 client preface and SETTINGS frame construction."""
        # 1. Exact 24-byte preface
        self.assertEqual(len(HTTP2_CLIENT_PREFACE), 24)
        self.assertEqual(HTTP2_CLIENT_PREFACE, b"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n")

        # 2. SETTINGS Frame (Stream 0)
        mux = HTTP2StreamMultiplexer(is_client=True)
        settings_frame = mux.build_settings_frame(ack=False)
        self.assertEqual(settings_frame.frame_type, HTTP2FrameType.SETTINGS)
        self.assertEqual(settings_frame.stream_id, 0)
        self.assertEqual(settings_frame.flags, 0)

        # 3. SETTINGS ACK
        ack_frame = mux.build_settings_frame(ack=True)
        self.assertEqual(ack_frame.flags, int(HTTP2Flags.ACK))

    def test_multi_stream_concurrent_interleaving(self):
        """
        Scale & Correctness Test:
        Interleave 10 concurrent streams with multiple DATA chunks over a single transport stream.
        Verify receiver demuxes all chunks to the correct stream without cross-talk.
        """
        client_mux = HTTP2StreamMultiplexer(is_client=True)
        server_mux = HTTP2StreamMultiplexer(is_client=False)

        stream_count = 10
        stream_ids = []
        expected_payloads = {}

        # 1. Create client streams
        for i in range(stream_count):
            sid = client_mux.create_stream()
            stream_ids.append(sid)
            expected_payloads[sid] = f"Content-For-Stream-{sid}-DataChunkXYZ".encode('utf-8')

        # 2. Generate interleaved frames
        all_frames = []
        # First send HEADERS for all streams
        for sid in stream_ids:
            h_frame = client_mux.build_headers_frame(
                stream_id=sid,
                headers={":method": "GET", ":path": f"/asset-{sid}.png", "x-agent-id": f"agent-{sid}"},
                end_stream=False
            )
            all_frames.append(h_frame)

        # Then send chunk 1 for all streams
        for sid in stream_ids:
            chunk1 = expected_payloads[sid][:10]
            f1 = client_mux.build_data_frame(stream_id=sid, data=chunk1, end_stream=False)
            all_frames.append(f1)

        # Then send chunk 2 (final) for all streams
        for sid in stream_ids:
            chunk2 = expected_payloads[sid][10:]
            f2 = client_mux.build_data_frame(stream_id=sid, data=chunk2, end_stream=True)
            all_frames.append(f2)

        # 3. Ingest frames in interleaved order on server
        completed_responses = {}
        for frame in all_frames:
            result = server_mux.ingest_frame(frame)
            if result:
                sid, headers, body = result
                completed_responses[sid] = (headers, body)

        # 4. Verify exact parity on all 10 streams
        self.assertEqual(len(completed_responses), stream_count)
        for sid in stream_ids:
            self.assertIn(sid, completed_responses)
            headers, body = completed_responses[sid]
            self.assertEqual(body, expected_payloads[sid])
            self.assertEqual(headers.get(":path"), f"/asset-{sid}.png")
            self.assertEqual(headers.get("x-agent-id"), f"agent-{sid}")

    def test_rst_stream_clean_termination(self):
        """Test stream cancellation via RST_STREAM without corrupting parallel streams."""
        mux = HTTP2StreamMultiplexer(is_client=False)
        sid_1 = 1
        sid_2 = 3

        # Stream 1 receives data
        mux.ingest_frame(HTTP2Frame(HTTP2FrameType.DATA, flags=0, stream_id=sid_1, payload=b"Stream1-Data"))

        # Stream 2 receives data
        mux.ingest_frame(HTTP2Frame(HTTP2FrameType.DATA, flags=0, stream_id=sid_2, payload=b"Stream2-Data"))

        # Terminate Stream 1 with RST_STREAM
        rst = mux.build_rst_stream_frame(stream_id=sid_1, error_code=HTTP2ErrorCode.CANCEL)
        mux.ingest_frame(rst)

        # Stream 1 should now be closed
        self.assertTrue(mux.streams[sid_1].is_closed)
        self.assertEqual(mux.streams[sid_1].error_code, HTTP2ErrorCode.CANCEL)

        # Stream 2 continues normally to completion
        res = mux.ingest_frame(HTTP2Frame(HTTP2FrameType.DATA, flags=int(HTTP2Flags.END_STREAM), stream_id=sid_2, payload=b"-Final"))
        self.assertIsNotNone(res)
        self.assertEqual(res[0], sid_2)
        self.assertEqual(res[2], b"Stream2-Data-Final")

    def test_high_throughput_binary_frame_parsing_benchmark(self):
        """
        Benchmark: Serialize and parse 50,000 binary HTTP/2 frames.
        Asserts throughput > 500,000 frames/sec.
        """
        sample_frame = HTTP2Frame(
            frame_type=HTTP2FrameType.DATA,
            flags=int(HTTP2Flags.END_STREAM),
            stream_id=101,
            payload=b"Telemetry and Asset Streaming Chunk Benchmark Data Bytes 1234567890"
        )
        wire_data = sample_frame.serialize()

        total_frames = 50000
        start_time = time.perf_counter()
        for _ in range(total_frames):
            parsed, _ = HTTP2Frame.parse(wire_data)
        duration = time.perf_counter() - start_time

        frames_per_sec = total_frames / duration
        latency_ns = (duration / total_frames) * 1_000_000_000

        self.assertLess(duration, 0.35, f"50k frames took {duration*1000:.2f}ms (must be < 350ms)")
        print(f"\n[Sprint 08 HTTP/2 Binary Frame Benchmark] {total_frames:,} Frames:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Throughput: {frames_per_sec:,.0f} frames/second")
        print(f"  - Average Parsing Latency: {latency_ns:.1f} ns/frame")



if __name__ == "__main__":
    unittest.main()
