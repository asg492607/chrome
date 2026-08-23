"""
PacketForge Raw Socket Layer & Packet Crafter Engine.
Provides bit-perfect binary packet serialization, deserialization, and
RFC 791 / RFC 768 one's complement 16-bit checksum algorithms with zero external dependencies.
"""

import struct
import socket
from typing import Tuple, Optional, Dict, Any

def compute_internet_checksum(data: bytes) -> int:
    """
    Computes the standard Internet 16-Bit One's Complement Checksum (RFC 791 / RFC 768).
    Used across IPv4, ICMP, UDP, and TCP headers.
    """
    if len(data) % 2 != 0:
        data = data + b'\x00'

    checksum = 0
    for i in range(0, len(data), 2):
        word = (data[i] << 8) + data[i + 1]
        checksum += word

    # Fold 32-bit sum to 16 bits
    while (checksum >> 16) > 0:
        checksum = (checksum & 0xFFFF) + (checksum >> 16)

    # One's complement invert
    return (~checksum) & 0xFFFF


def mac_str_to_bytes(mac_str: str) -> bytes:
    """Converts '00:1A:2B:3C:4D:5E' or '00-1a-2b-3c-4d-5e' to 6 raw bytes."""
    clean = mac_str.replace(":", "").replace("-", "")
    return bytes.fromhex(clean)


def bytes_to_mac_str(b: bytes) -> str:
    """Converts 6 raw bytes to '00:1A:2B:3C:4D:5E'."""
    return ":".join(f"{x:02X}" for x in b[:6])


def ip_str_to_bytes(ip_str: str) -> bytes:
    """Converts IPv4 string '192.168.1.1' to 4 raw bytes."""
    return socket.inet_aton(ip_str)


def bytes_to_ip_str(b: bytes) -> str:
    """Converts 4 raw bytes to IPv4 string '192.168.1.1'."""
    return socket.inet_ntoa(b[:4])


class EthernetFrame:
    """
    Ethernet II Frame Header (Exact 14 Bytes):
    - [00..05] Destination MAC (6 Bytes)
    - [06..11] Source MAC      (6 Bytes)
    - [12..13] EtherType       (2 Bytes, e.g. 0x0800 for IPv4, 0x0806 for ARP)
    """
    ETHERTYPE_IPV4: int = 0x0800
    ETHERTYPE_ARP: int = 0x0806

    def __init__(
        self,
        dst_mac: str = "FF:FF:FF:FF:FF:FF",
        src_mac: str = "00:11:22:33:44:55",
        ethertype: int = ETHERTYPE_IPV4,
        payload: bytes = b""
    ):
        self.dst_mac = dst_mac
        self.src_mac = src_mac
        self.ethertype = ethertype
        self.payload = payload

    def serialize(self) -> bytes:
        header = struct.pack(
            "!6s6sH",
            mac_str_to_bytes(self.dst_mac),
            mac_str_to_bytes(self.src_mac),
            self.ethertype
        )
        return header + self.payload

    @classmethod
    def parse(cls, raw: bytes) -> "EthernetFrame":
        if len(raw) < 14:
            raise ValueError("Raw buffer too short for Ethernet II header (< 14 bytes).")
        dst_bytes, src_bytes, ethertype = struct.unpack("!6s6sH", raw[:14])
        return cls(
            dst_mac=bytes_to_mac_str(dst_bytes),
            src_mac=bytes_to_mac_str(src_bytes),
            ethertype=ethertype,
            payload=raw[14:]
        )


class IPv4Packet:
    """
    IPv4 Packet Header (Exact 20 Bytes without options):
    - [00]     Version (4 bits) + IHL (4 bits)
    - [01]     DSCP (6 bits) + ECN (2 bits)
    - [02..03] Total Length (2 Bytes)
    - [04..05] Identification (2 Bytes)
    - [06..07] Flags (3 bits) + Fragment Offset (13 bits)
    - [08]     Time to Live (TTL)
    - [09]     Protocol (1 Byte: UDP=17, TCP=6, ICMP=1)
    - [10..11] Header Checksum (2 Bytes)
    - [12..15] Source IP (4 Bytes)
    - [16..19] Destination IP (4 Bytes)
    """
    PROTO_ICMP: int = 1
    PROTO_TCP: int = 6
    PROTO_UDP: int = 17

    def __init__(
        self,
        src_ip: str = "192.168.1.100",
        dst_ip: str = "192.168.1.1",
        protocol: int = PROTO_UDP,
        ttl: int = 64,
        identification: int = 0x1234,
        flags: int = 2,  # Don't Fragment (DF)
        payload: bytes = b""
    ):
        self.version: int = 4
        self.ihl: int = 5  # 5 * 4 = 20 bytes
        self.dscp_ecn: int = 0
        self.identification: int = identification
        self.flags: int = flags
        self.fragment_offset: int = 0
        self.ttl: int = ttl
        self.protocol: int = protocol
        self.checksum: int = 0
        self.src_ip: str = src_ip
        self.dst_ip: str = dst_ip
        self.payload: bytes = payload

    def serialize(self) -> bytes:
        total_length = (self.ihl * 4) + len(self.payload)
        ver_ihl = (self.version << 4) | (self.ihl & 0x0F)
        flags_frag = ((self.flags & 0x07) << 13) | (self.fragment_offset & 0x1FFF)
        src_bytes = ip_str_to_bytes(self.src_ip)
        dst_bytes = ip_str_to_bytes(self.dst_ip)

        # 1. Build header with checksum = 0
        header_no_chk = struct.pack(
            "!BBHHHBBH4s4s",
            ver_ihl,
            self.dscp_ecn,
            total_length,
            self.identification,
            flags_frag,
            self.ttl,
            self.protocol,
            0,
            src_bytes,
            dst_bytes
        )

        # 2. Compute RFC 791 Checksum over header
        self.checksum = compute_internet_checksum(header_no_chk)

        # 3. Pack header with calculated checksum
        header_final = struct.pack(
            "!BBHHHBBH4s4s",
            ver_ihl,
            self.dscp_ecn,
            total_length,
            self.identification,
            flags_frag,
            self.ttl,
            self.protocol,
            self.checksum,
            src_bytes,
            dst_bytes
        )
        return header_final + self.payload

    @classmethod
    def parse(cls, raw: bytes) -> "IPv4Packet":
        if len(raw) < 20:
            raise ValueError("Raw buffer too short for IPv4 header (< 20 bytes).")
        ver_ihl, dscp_ecn, total_length, ident, flags_frag, ttl, proto, chk, src_b, dst_b = struct.unpack(
            "!BBHHHBBH4s4s", raw[:20]
        )
        version = ver_ihl >> 4
        ihl = ver_ihl & 0x0F
        if version != 4:
            raise ValueError(f"Invalid IP version: {version}")

        header_bytes = raw[:ihl * 4]
        flags = flags_frag >> 13

        pkt = cls(
            src_ip=bytes_to_ip_str(src_b),
            dst_ip=bytes_to_ip_str(dst_b),
            protocol=proto,
            ttl=ttl,
            identification=ident,
            flags=flags,
            payload=raw[ihl * 4:total_length]
        )
        pkt.checksum = chk

        # Checksum validation
        calculated = compute_internet_checksum(header_bytes)
        if calculated != 0:
            raise ValueError(f"IPv4 Checksum Mismatch: header corrupted (residual={calculated:#06x})")

        return pkt


class UDPPacket:
    """
    UDP Packet Header (Exact 8 Bytes):
    - [00..01] Source Port      (2 Bytes)
    - [02..03] Destination Port (2 Bytes)
    - [04..05] Length           (2 Bytes)
    - [06..07] UDP Checksum     (2 Bytes)
    """
    def __init__(
        self,
        src_port: int = 5353,
        dst_port: int = 5353,
        payload: bytes = b""
    ):
        self.src_port: int = src_port
        self.dst_port: int = dst_port
        self.checksum: int = 0
        self.payload: bytes = payload

    def serialize(self, src_ip: Optional[str] = None, dst_ip: Optional[str] = None) -> bytes:
        length = 8 + len(self.payload)
        header_no_chk = struct.pack("!HHHH", self.src_port, self.dst_port, length, 0)
        
        # Calculate checksum with IPv4 Pseudo-Header if IPs provided
        if src_ip and dst_ip:
            pseudo = struct.pack(
                "!4s4sBBH",
                ip_str_to_bytes(src_ip),
                ip_str_to_bytes(dst_ip),
                0,
                IPv4Packet.PROTO_UDP,
                length
            )
            self.checksum = compute_internet_checksum(pseudo + header_no_chk + self.payload)
        else:
            self.checksum = 0

        header_final = struct.pack("!HHHH", self.src_port, self.dst_port, length, self.checksum)
        return header_final + self.payload

    @classmethod
    def parse(cls, raw: bytes) -> "UDPPacket":
        if len(raw) < 8:
            raise ValueError("Raw buffer too short for UDP header (< 8 bytes).")
        src_p, dst_p, length, chk = struct.unpack("!HHHH", raw[:8])
        pkt = cls(src_port=src_p, dst_port=dst_p, payload=raw[8:length])
        pkt.checksum = chk
        return pkt


class TCPPacket:
    """
    TCP Packet Header (Exact 20 Bytes without options):
    - [00..01] Source Port (2 Bytes)
    - [02..03] Destination Port (2 Bytes)
    - [04..07] Sequence Number (4 Bytes)
    - [08..11] Acknowledgment Number (4 Bytes)
    - [12..13] Data Offset (4 bits) + Reserved (3 bits) + Flags (9 bits: URG, ACK, PSH, RST, SYN, FIN)
    - [14..15] Window Size (2 Bytes)
    - [16..17] TCP Checksum (2 Bytes)
    - [18..19] Urgent Pointer (2 Bytes)
    """
    FLAG_FIN: int = 0x01
    FLAG_SYN: int = 0x02
    FLAG_RST: int = 0x04
    FLAG_PSH: int = 0x08
    FLAG_ACK: int = 0x10
    FLAG_URG: int = 0x20

    def __init__(
        self,
        src_port: int = 8080,
        dst_port: int = 80,
        seq_num: int = 1000,
        ack_num: int = 0,
        flags: int = FLAG_SYN,
        window_size: int = 65535,
        payload: bytes = b""
    ):
        self.src_port: int = src_port
        self.dst_port: int = dst_port
        self.seq_num: int = seq_num
        self.ack_num: int = ack_num
        self.data_offset: int = 5  # 5 * 4 = 20 bytes
        self.flags: int = flags
        self.window_size: int = window_size
        self.checksum: int = 0
        self.urgent_ptr: int = 0
        self.payload: bytes = payload

    def serialize(self, src_ip: Optional[str] = None, dst_ip: Optional[str] = None) -> bytes:
        offset_flags = (self.data_offset << 12) | (self.flags & 0x01FF)
        header_no_chk = struct.pack(
            "!HHIIHHHH",
            self.src_port,
            self.dst_port,
            self.seq_num,
            self.ack_num,
            offset_flags,
            self.window_size,
            0,
            self.urgent_ptr
        )

        if src_ip and dst_ip:
            tcp_length = len(header_no_chk) + len(self.payload)
            pseudo = struct.pack(
                "!4s4sBBH",
                ip_str_to_bytes(src_ip),
                ip_str_to_bytes(dst_ip),
                0,
                IPv4Packet.PROTO_TCP,
                tcp_length
            )
            self.checksum = compute_internet_checksum(pseudo + header_no_chk + self.payload)
        else:
            self.checksum = 0

        header_final = struct.pack(
            "!HHIIHHHH",
            self.src_port,
            self.dst_port,
            self.seq_num,
            self.ack_num,
            offset_flags,
            self.window_size,
            self.checksum,
            self.urgent_ptr
        )
        return header_final + self.payload

    @classmethod
    def parse(cls, raw: bytes) -> "TCPPacket":
        if len(raw) < 20:
            raise ValueError("Raw buffer too short for TCP header (< 20 bytes).")
        src_p, dst_p, seq, ack, offset_flags, win, chk, urg = struct.unpack("!HHIIHHHH", raw[:20])
        data_offset = offset_flags >> 12
        flags = offset_flags & 0x01FF
        
        pkt = cls(
            src_port=src_p,
            dst_port=dst_p,
            seq_num=seq,
            ack_num=ack,
            flags=flags,
            window_size=win,
            payload=raw[data_offset * 4:]
        )
        pkt.checksum = chk
        pkt.data_offset = data_offset
        return pkt


class PacketForgeEngine:
    """
    High-level PacketForge orchestrator.
    Constructs full-stack Ethernet/IP/UDP/TCP frames and bridges raw frames to LockFreeRingBuffer descriptors.
    """

    @staticmethod
    def build_udp_frame(
        src_mac: str, dst_mac: str,
        src_ip: str, dst_ip: str,
        src_port: int, dst_port: int,
        payload: bytes
    ) -> bytes:
        """Constructs full Ethernet II + IPv4 + UDP packet."""
        udp = UDPPacket(src_port=src_port, dst_port=dst_port, payload=payload)
        udp_bytes = udp.serialize(src_ip=src_ip, dst_ip=dst_ip)
        
        ipv4 = IPv4Packet(src_ip=src_ip, dst_ip=dst_ip, protocol=IPv4Packet.PROTO_UDP, payload=udp_bytes)
        ip_bytes = ipv4.serialize()

        eth = EthernetFrame(src_mac=src_mac, dst_mac=dst_mac, ethertype=EthernetFrame.ETHERTYPE_IPV4, payload=ip_bytes)
        return eth.serialize()

    @staticmethod
    def build_tcp_syn_frame(
        src_mac: str, dst_mac: str,
        src_ip: str, dst_ip: str,
        src_port: int, dst_port: int,
        seq_num: int = 1000
    ) -> bytes:
        """Constructs full Ethernet II + IPv4 + TCP SYN handshake packet."""
        tcp = TCPPacket(src_port=src_port, dst_port=dst_port, seq_num=seq_num, flags=TCPPacket.FLAG_SYN)
        tcp_bytes = tcp.serialize(src_ip=src_ip, dst_ip=dst_ip)

        ipv4 = IPv4Packet(src_ip=src_ip, dst_ip=dst_ip, protocol=IPv4Packet.PROTO_TCP, payload=tcp_bytes)
        ip_bytes = ipv4.serialize()

        eth = EthernetFrame(src_mac=src_mac, dst_mac=dst_mac, ethertype=EthernetFrame.ETHERTYPE_IPV4, payload=ip_bytes)
        return eth.serialize()
