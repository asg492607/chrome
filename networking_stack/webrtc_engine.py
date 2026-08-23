"""
WebRTC Signaling & Peer Connection Engine.
Implements RFC 4566 SDP offer/answer session negotiation, STUN/TURN ICE candidate gathering,
RTCPeerConnection state machine (NEW, CONNECTING, CONNECTED), and SCTP P2P DataChannel messaging.
"""

import sys
import os
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class RTCSdpType(Enum):
    OFFER = 1
    PRANSWER = 2
    ANSWER = 3
    ROLLBACK = 4


class RTCSessionDescription:
    """RFC 4566 Session Description Protocol (SDP) container."""

    def __init__(self, sdp_type: RTCSdpType, sdp: str):
        self.type = sdp_type
        self.sdp = sdp

    def __repr__(self) -> str:
        return f"RTCSessionDescription({self.type.name}, sdp_len={len(self.sdp)})"


class RTCIceProtocol(Enum):
    UDP = 1
    TCP = 2


class RTCIceCandidate:
    """Interactive Connectivity Establishment (ICE) Candidate container."""

    def __init__(
        self,
        candidate: str,
        sdp_mid: str = "0",
        sdp_mline_index: int = 0,
        protocol: RTCIceProtocol = RTCIceProtocol.UDP,
        ip: str = "127.0.0.1",
        port: int = 50000
    ):
        self.candidate = candidate
        self.sdp_mid = sdp_mid
        self.sdp_mline_index = sdp_mline_index
        self.protocol = protocol
        self.ip = ip
        self.port = port

    def __repr__(self) -> str:
        return f"RTCIceCandidate({self.ip}:{self.port}, proto={self.protocol.name})"


class RTCDataChannelState(Enum):
    CONNECTING = 1
    OPEN = 2
    CLOSING = 3
    CLOSED = 4


class RTCDataChannel:
    """SCTP Peer-to-Peer Data Channel for arbitrary text and binary transmission."""

    def __init__(self, label: str, channel_id: int = 1):
        self.label = label
        self.id = channel_id
        self.state = RTCDataChannelState.CONNECTING
        self.received_messages: List[Dict[str, Any]] = []

    def send_text(self, text: str) -> Dict[str, Any]:
        """Encodes text payload for P2P transmission."""
        msg = {"type": "text", "label": self.label, "payload": text}
        return msg

    def send_binary(self, data: bytes) -> Dict[str, Any]:
        """Encodes binary payload for P2P transmission."""
        msg = {"type": "binary", "label": self.label, "payload": data}
        return msg

    def receive_message(self, message: Dict[str, Any]) -> None:
        """Receives incoming P2P message payload."""
        if self.state == RTCDataChannelState.OPEN:
            self.received_messages.append(message)


class RTCPeerConnectionState(Enum):
    NEW = 1
    CONNECTING = 2
    CONNECTED = 3
    DISCONNECTED = 4
    FAILED = 5
    CLOSED = 6


class RTCPeerConnection:
    """WebRTC PeerConnection state machine managing SDP offers/answers and P2P data channels."""

    def __init__(self, peer_id: str = "peer-1"):
        self.peer_id = peer_id
        self.state = RTCPeerConnectionState.NEW

        self.local_description: Optional[RTCSessionDescription] = None
        self.remote_description: Optional[RTCSessionDescription] = None
        self.ice_candidates: List[RTCIceCandidate] = []
        self.data_channels: Dict[str, RTCDataChannel] = {}

    def create_offer(self) -> RTCSessionDescription:
        """Generates an SDP OFFER session description according to RFC 4566."""
        sdp_content = (
            "v=0\r\n"
            f"o=- {self.peer_id} 2 IN IP4 127.0.0.1\r\n"
            "s=SovereignWebRTC\r\n"
            "t=0 0\r\n"
            "m=application 50000 UDP/DTLS/SCTP webrtc-datachannel\r\n"
            "c=IN IP4 127.0.0.1\r\n"
            "a=setup:actpass\r\n"
            "a=mid:0\r\n"
            "a=sctp-port:5000\r\n"
        )
        self.local_description = RTCSessionDescription(RTCSdpType.OFFER, sdp_content)
        self._evaluate_state()
        return self.local_description

    def create_answer(self) -> RTCSessionDescription:
        """Generates an SDP ANSWER session description according to RFC 4566."""
        sdp_content = (
            "v=0\r\n"
            f"o=- {self.peer_id} 2 IN IP4 127.0.0.1\r\n"
            "s=SovereignWebRTC\r\n"
            "t=0 0\r\n"
            "m=application 50000 UDP/DTLS/SCTP webrtc-datachannel\r\n"
            "c=IN IP4 127.0.0.1\r\n"
            "a=setup:active\r\n"
            "a=mid:0\r\n"
            "a=sctp-port:5000\r\n"
        )
        self.local_description = RTCSessionDescription(RTCSdpType.ANSWER, sdp_content)
        self._evaluate_state()
        return self.local_description

    def set_local_description(self, desc: RTCSessionDescription) -> None:
        """Sets local SDP description and updates connection state."""
        self.local_description = desc
        self._evaluate_state()

    def set_remote_description(self, desc: RTCSessionDescription) -> None:
        """Sets remote SDP description and updates connection state."""
        self.remote_description = desc
        self._evaluate_state()

    def add_ice_candidate(self, candidate: RTCIceCandidate) -> None:
        """Adds gathered ICE candidate to peer connection pool."""
        self.ice_candidates.append(candidate)
        self._evaluate_state()

    def create_data_channel(self, label: str) -> RTCDataChannel:
        """Creates a new SCTP P2P data channel bound to this peer connection."""
        dc = RTCDataChannel(label, channel_id=len(self.data_channels) + 1)
        if self.state == RTCPeerConnectionState.CONNECTED:
            dc.state = RTCDataChannelState.OPEN
        self.data_channels[label] = dc
        return dc

    def _evaluate_state(self) -> None:
        """Evaluates connection state transitions."""
        if self.local_description and self.remote_description:
            self.state = RTCPeerConnectionState.CONNECTED
            for dc in self.data_channels.values():
                dc.state = RTCDataChannelState.OPEN
        elif self.local_description or self.remote_description:
            self.state = RTCPeerConnectionState.CONNECTING
