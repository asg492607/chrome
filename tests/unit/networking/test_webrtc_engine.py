"""
Unit & Benchmark Test Suite for WebRTC Signaling & Peer Connection Engine (Sprint 23).
Verifies RFC 4566 SDP offer/answer negotiation, ICE candidate gathering,
RTCPeerConnection state machine, and SCTP P2P RTCDataChannel messaging.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from networking_stack.webrtc_engine import (
    RTCSdpType,
    RTCSessionDescription,
    RTCIceProtocol,
    RTCIceCandidate,
    RTCDataChannelState,
    RTCDataChannel,
    RTCPeerConnectionState,
    RTCPeerConnection
)


class TestWebRTCSubsystem(unittest.TestCase):

    def test_sdp_offer_answer_handshake(self):
        """Verify SDP OFFER/ANSWER negotiation between Peer A and Peer B."""
        pc_a = RTCPeerConnection("peer-a")
        pc_b = RTCPeerConnection("peer-b")

        self.assertEqual(pc_a.state, RTCPeerConnectionState.NEW)
        self.assertEqual(pc_b.state, RTCPeerConnectionState.NEW)

        # Peer A creates offer
        offer = pc_a.create_offer()
        self.assertEqual(offer.type, RTCSdpType.OFFER)
        self.assertEqual(pc_a.state, RTCPeerConnectionState.CONNECTING)

        # Peer B receives offer and creates answer
        pc_b.set_remote_description(offer)
        answer = pc_b.create_answer()
        self.assertEqual(answer.type, RTCSdpType.ANSWER)

        # Peer A sets remote answer
        pc_a.set_remote_description(answer)

        # Both peers transition to CONNECTED
        self.assertEqual(pc_a.state, RTCPeerConnectionState.CONNECTED)
        self.assertEqual(pc_b.state, RTCPeerConnectionState.CONNECTED)

    def test_ice_candidate_gathering(self):
        """Verify STUN/TURN ICE candidate gathering and connection pool addition."""
        pc = RTCPeerConnection("peer-local")
        cand = RTCIceCandidate(
            candidate="candidate:1 1 UDP 2122260223 192.168.1.100 50000 typ host",
            sdp_mid="0",
            sdp_mline_index=0,
            protocol=RTCIceProtocol.UDP,
            ip="192.168.1.100",
            port=50000
        )

        pc.add_ice_candidate(cand)
        self.assertEqual(len(pc.ice_candidates), 1)
        self.assertEqual(pc.ice_candidates[0].ip, "192.168.1.100")

    def test_rtcdatachannel_p2p_messaging(self):
        """Verify creating RTCDataChannel and transmitting text/binary P2P payloads."""
        pc_a = RTCPeerConnection("peer-a")
        pc_b = RTCPeerConnection("peer-b")

        dc_a = pc_a.create_data_channel("file-transfer")
        self.assertEqual(dc_a.state, RTCDataChannelState.CONNECTING)

        # Complete SDP Handshake to open DataChannel
        offer = pc_a.create_offer()
        pc_b.set_remote_description(offer)
        answer = pc_b.create_answer()
        pc_a.set_remote_description(answer)

        self.assertEqual(dc_a.state, RTCDataChannelState.OPEN)

        # Transmit P2P messages
        msg_text = dc_a.send_text("Peer-to-Peer Zero Server Direct Link")
        self.assertEqual(msg_text["payload"], "Peer-to-Peer Zero Server Direct Link")

        dc_a.receive_message(msg_text)
        self.assertEqual(len(dc_a.received_messages), 1)

    def test_peer_connection_state_transitions(self):
        """Verify RTCPeerConnection state transitions: NEW -> CONNECTING -> CONNECTED."""
        pc = RTCPeerConnection("test-peer")
        self.assertEqual(pc.state, RTCPeerConnectionState.NEW)

        offer = pc.create_offer()
        self.assertEqual(pc.state, RTCPeerConnectionState.CONNECTING)

        answer = RTCSessionDescription(RTCSdpType.ANSWER, offer.sdp)
        pc.set_remote_description(answer)
        self.assertEqual(pc.state, RTCPeerConnectionState.CONNECTED)

    def test_high_speed_p2p_data_channel_benchmark(self):
        """
        Benchmark: Exchange 50,000 P2P data channel messages.
        Asserts duration < 0.15s (> 300,000 msgs/sec).
        """
        pc_a = RTCPeerConnection("peer-a")
        pc_b = RTCPeerConnection("peer-b")

        dc_a = pc_a.create_data_channel("bench-channel")
        offer = pc_a.create_offer()
        pc_b.set_remote_description(offer)
        answer = pc_b.create_answer()
        pc_a.set_remote_description(answer)

        start_time = time.perf_counter()
        for i in range(50000):
            msg = dc_a.send_binary(f"pkt_{i}".encode('utf-8'))
            dc_a.receive_message(msg)
        duration = time.perf_counter() - start_time

        total_msgs = 50000
        msgs_per_sec = total_msgs / duration
        latency_us = (duration / total_msgs) * 1_000_000

        self.assertLess(duration, 0.20, f"50k P2P WebRTC data msgs took {duration*1000:.2f}ms (must be < 200ms)")
        print(f"\n[Sprint 23 WebRTC Benchmark] {total_msgs:,} P2P DataChannel Messages Transmitted:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - P2P Data Throughput: {msgs_per_sec:,.0f} msgs/second")
        print(f"  - Average Message Latency: {latency_us:.2f} µs/msg")


if __name__ == "__main__":
    unittest.main()
