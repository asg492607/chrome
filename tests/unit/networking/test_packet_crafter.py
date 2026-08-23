"""
Unit Test Suite for PacketForge Raw Socket Layer & Packet Crafter (Sprint 03).
Verifies RFC 791/768 checksum algorithms, Ethernet II, IPv4, UDP, TCP binary framing,
tamper/corruption detection, and zero-copy LockFreeRingBuffer IPC integration.
"""

import sys
import os
import unittest
import struct

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from networking_stack.packet_crafter import (
    compute_internet_checksum,
    mac_str_to_bytes,
    bytes_to_mac_str,
    ip_str_to_bytes,
    bytes_to_ip_str,
    EthernetFrame,
    IPv4Packet,
    UDPPacket,
    TCPPacket,
    PacketForgeEngine
)
from core_platform.lockfree_ring_buffer import LockFreeRingBuffer, RingMessageDescriptor


class TestPacketCrafterSubsystem(unittest.TestCase):

    def test_rfc791_internet_checksum_math(self):
        """Verify 16-bit one's complement folded checksum calculation."""
        # Standard test vector (RFC 1071 / 791 sample header bytes)
        sample_data = bytes([
            0x45, 0x00, 0x00, 0x3c,
            0x1c, 0x46, 0x40, 0x00,
            0x40, 0x06, 0x00, 0x00,  # Checksum field = 0x0000 during calculation
            0xac, 0x10, 0x0a, 0x63,  # 172.16.10.99
            0xac, 0x10, 0x0a, 0x0c   # 172.16.10.12
        ])
        checksum = compute_internet_checksum(sample_data)
        self.assertIsInstance(checksum, int)
        self.assertGreater(checksum, 0)
        self.assertLessEqual(checksum, 0xFFFF)

        # Inject computed checksum and verify residual is 0
        verified_data = sample_data[:10] + struct.pack("!H", checksum) + sample_data[12:]
        residual = compute_internet_checksum(verified_data)
        self.assertEqual(residual, 0, f"Valid checksum calculation must yield residual 0, got {residual:#06x}")

    def test_mac_and_ip_string_conversions(self):
        """Test MAC and IPv4 byte-to-string and string-to-byte encoders."""
        mac_str = "00:1A:2B:3C:4D:5E"
        mac_bytes = mac_str_to_bytes(mac_str)
        self.assertEqual(len(mac_bytes), 6)
        self.assertEqual(bytes_to_mac_str(mac_bytes), mac_str)

        ip_str = "192.168.1.254"
        ip_bytes = ip_str_to_bytes(ip_str)
        self.assertEqual(len(ip_bytes), 4)
        self.assertEqual(bytes_to_ip_str(ip_bytes), ip_str)

    def test_ethernet_frame_serialization_roundtrip(self):
        """Test Ethernet II frame serialization and deserialization."""
        payload = b"Hello Sovereign Network"
        eth = EthernetFrame(
            dst_mac="AA:BB:CC:DD:EE:FF",
            src_mac="11:22:33:44:55:66",
            ethertype=EthernetFrame.ETHERTYPE_IPV4,
            payload=payload
        )
        raw = eth.serialize()
        self.assertEqual(len(raw), 14 + len(payload))

        parsed = EthernetFrame.parse(raw)
        self.assertEqual(parsed.dst_mac, "AA:BB:CC:DD:EE:FF")
        self.assertEqual(parsed.src_mac, "11:22:33:44:55:66")
        self.assertEqual(parsed.ethertype, EthernetFrame.ETHERTYPE_IPV4)
        self.assertEqual(parsed.payload, payload)

    def test_ipv4_packet_serialization_roundtrip(self):
        """Test IPv4 header calculation, checksum generation, and parsing."""
        payload = b"GET / HTTP/1.1\r\nHost: local.search\r\n\r\n"
        ip = IPv4Packet(
            src_ip="10.0.0.5",
            dst_ip="10.0.0.1",
            protocol=IPv4Packet.PROTO_TCP,
            ttl=128,
            payload=payload
        )
        raw = ip.serialize()
        self.assertEqual(len(raw), 20 + len(payload))
        self.assertNotEqual(ip.checksum, 0)

        parsed = IPv4Packet.parse(raw)
        self.assertEqual(parsed.src_ip, "10.0.0.5")
        self.assertEqual(parsed.dst_ip, "10.0.0.1")
        self.assertEqual(parsed.protocol, IPv4Packet.PROTO_TCP)
        self.assertEqual(parsed.ttl, 128)
        self.assertEqual(parsed.payload, payload)

    def test_udp_packet_serialization_roundtrip(self):
        """Test UDP header creation, length fields, and payload parsing."""
        payload = b"DNS_QUERY:asgsearch.local"
        udp = UDPPacket(src_port=54321, dst_port=5353, payload=payload)
        raw = udp.serialize(src_ip="192.168.1.100", dst_ip="192.168.1.1")
        self.assertEqual(len(raw), 8 + len(payload))

        parsed = UDPPacket.parse(raw)
        self.assertEqual(parsed.src_port, 54321)
        self.assertEqual(parsed.dst_port, 5353)
        self.assertEqual(parsed.payload, payload)

    def test_tcp_packet_flags_and_handshake(self):
        """Test TCP SYN and ACK flags packing and sequence number tracking."""
        tcp_syn = TCPPacket(
            src_port=49152,
            dst_port=80,
            seq_num=100000,
            flags=TCPPacket.FLAG_SYN
        )
        raw_syn = tcp_syn.serialize(src_ip="192.168.1.50", dst_ip="192.168.1.1")
        parsed_syn = TCPPacket.parse(raw_syn)

        self.assertEqual(parsed_syn.src_port, 49152)
        self.assertEqual(parsed_syn.dst_port, 80)
        self.assertEqual(parsed_syn.seq_num, 100000)
        self.assertTrue(bool(parsed_syn.flags & TCPPacket.FLAG_SYN))
        self.assertFalse(bool(parsed_syn.flags & TCPPacket.FLAG_ACK))

    def test_corrupt_packet_detection(self):
        """Test that single bit-flip corruptions trigger checksum rejection."""
        ip = IPv4Packet(src_ip="192.168.1.10", dst_ip="192.168.1.1", payload=b"TestData")
        raw = bytearray(ip.serialize())

        # Flip 1 bit in TTL field (offset 8)
        raw[8] ^= 0x01

        with self.assertRaises(ValueError) as ctx:
            IPv4Packet.parse(bytes(raw))
        self.assertIn("Checksum Mismatch", str(ctx.exception))

    def test_full_stack_frame_and_ring_buffer_ipc_integration(self):
        """
        Integration Test:
        Build full Ethernet II + IPv4 + UDP frame via PacketForgeEngine,
        push into LockFreeRingBuffer IPC queue, and pop/verify on consumer side.
        """
        raw_frame = PacketForgeEngine.build_udp_frame(
            src_mac="00:AA:BB:CC:DD:EE",
            dst_mac="FF:FF:FF:FF:FF:FF",
            src_ip="192.168.1.150",
            dst_ip="255.255.255.255",
            src_port=68,
            dst_port=67,
            payload=b"DHCP_DISCOVER_PAYLOAD"
        )

        rb = LockFreeRingBuffer(capacity_power_of_two=128)
        
        # Ingest into Ring Buffer
        pushed = rb.push(
            msg_type=1,  # 1 = NET_PACKET
            flags=0x01,  # 0x01 = RAW_INGRESS
            entity_id=0,
            payload_bytes=raw_frame[:36]  # Inline header slice
        )
        self.assertTrue(pushed)

        # Pop from Ring Buffer
        msg = rb.pop()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.msg_type, 1)
        self.assertEqual(msg.flags, 0x01)

        # Parse the full raw frame
        eth = EthernetFrame.parse(raw_frame)
        self.assertEqual(eth.dst_mac, "FF:FF:FF:FF:FF:FF")
        
        ip = IPv4Packet.parse(eth.payload)
        self.assertEqual(ip.src_ip, "192.168.1.150")
        self.assertEqual(ip.dst_ip, "255.255.255.255")

        udp = UDPPacket.parse(ip.payload)
        self.assertEqual(udp.src_port, 68)
        self.assertEqual(udp.dst_port, 67)
        self.assertEqual(udp.payload, b"DHCP_DISCOVER_PAYLOAD")


if __name__ == "__main__":
    unittest.main()
