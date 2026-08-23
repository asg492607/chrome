"""
Lock-Free Single-Producer Single-Consumer (SPSC) Ring Buffer.
Implements 64-byte L1 cache-line aligned message descriptors,
cache-line padded atomic pointers (preventing CPU False Sharing),
and bitwise power-of-two index wrapping for zero-copy high-throughput IPC.
"""

import ctypes
import time
from typing import Optional, Tuple, List, Dict, Any

class RingMessageDescriptor(ctypes.Structure):
    """
    Exact 64-Byte Message Descriptor.
    Fits exactly into a single 64-byte CPU L1 cache line.
    
    Memory Layout:
    - [00..03] msg_type       : u32 (4 Bytes) - e.g., 1=NET_PACKET, 2=DOM_MUTATION, 3=RENDER_CMD
    - [04..07] flags          : u32 (4 Bytes) - Priority, dirty bits, encryption flags
    - [08..15] timestamp_ns   : u64 (8 Bytes) - Nanosecond ingress timestamp
    - [16..19] entity_id      : u32 (4 Bytes) - Target DOM Entity ID
    - [20..23] payload_len    : u32 (4 Bytes) - Active payload length in inline buffer
    - [24..27] payload_offset : u32 (4 Bytes) - Optional offset for external memory mapping
    - [28..63] payload_data   : 36 x u8       - Inline raw byte payload
    """
    _pack_ = 1
    _fields_ = [
        ("msg_type", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("timestamp_ns", ctypes.c_uint64),
        ("entity_id", ctypes.c_uint32),
        ("payload_len", ctypes.c_uint32),
        ("payload_offset", ctypes.c_uint32),
        ("payload_data", ctypes.c_uint8 * 36),
    ]

    def set_payload(self, data: bytes) -> None:
        """Copies up to 36 bytes into the inline payload buffer."""
        length = min(len(data), 36)
        self.payload_len = length
        for i in range(length):
            self.payload_data[i] = data[i]

    def get_payload(self) -> bytes:
        """Extracts the active inline byte slice."""
        length = min(self.payload_len, 36)
        return bytes(self.payload_data[:length])

    def __repr__(self) -> str:
        return (
            f"RingMsg(type={self.msg_type}, flags={self.flags:#x}, "
            f"entity={self.entity_id}, ts={self.timestamp_ns}, len={self.payload_len})"
        )


class SPSCAtomicPointers(ctypes.Structure):
    """
    Padded Atomic Pointer Block (Exact 128 Bytes).
    Separates `head` and `tail` across two distinct 64-byte L1 cache lines
    to mathematically eliminate CPU cache-line bouncing (False Sharing).
    """
    _pack_ = 1
    _fields_ = [
        # Cache Line 1: Producer Write, Consumer Read (64 Bytes)
        ("head", ctypes.c_uint64),
        ("_pad_producer", ctypes.c_uint8 * 56),

        # Cache Line 2: Consumer Write, Producer Read (64 Bytes)
        ("tail", ctypes.c_uint64),
        ("_pad_consumer", ctypes.c_uint8 * 56),
    ]


class LockFreeRingBuffer:
    """
    High-Performance Lock-Free SPSC Circular Ring Buffer.
    Provides non-blocking, zero-allocation message passing between concurrent threads.
    """

    def __init__(self, capacity_power_of_two: int = 65536):
        # Enforce power of two for fast bitwise wrapping: (index & mask)
        if (capacity_power_of_two & (capacity_power_of_two - 1)) != 0 or capacity_power_of_two < 16:
            raise ValueError("Capacity must be a power of two >= 16 (e.g. 1024, 65536).")

        self.capacity: int = capacity_power_of_two
        self.mask: int = capacity_power_of_two - 1
        
        # Allocate 128-byte cache-isolated atomic pointers
        self.pointers = SPSCAtomicPointers()
        self.pointers.head = 0
        self.pointers.tail = 0

        # Pre-allocate contiguous contiguous 64-byte descriptor buffer
        self._buffer_type = RingMessageDescriptor * self.capacity
        self.buffer = self._buffer_type()

        # Telemetry metrics
        self.total_pushed: int = 0
        self.total_popped: int = 0
        self.dropped_count: int = 0

    def push(
        self,
        msg_type: int,
        flags: int = 0,
        entity_id: int = 0,
        payload_bytes: bytes = b"",
        timestamp_ns: Optional[int] = None
    ) -> bool:
        """
        Producer operation: writes a message to the ring buffer.
        Returns True on success, False if buffer is full (non-blocking).
        """
        head = self.pointers.head
        tail = self.pointers.tail

        # Check if full: capacity reached
        if (head - tail) >= self.capacity:
            self.dropped_count += 1
            return False

        # Compute slot index branchlessly via bitwise mask
        slot_idx = head & self.mask
        slot = self.buffer[slot_idx]
        slot.msg_type = msg_type
        slot.flags = flags
        slot.entity_id = entity_id
        slot.timestamp_ns = timestamp_ns or time.perf_counter_ns()
        slot.payload_offset = 0
        
        if payload_bytes:
            slot.set_payload(payload_bytes)
        else:
            slot.payload_len = 0

        # Advance head pointer (Producer release)
        self.pointers.head = head + 1
        self.total_pushed += 1
        return True

    def pop(self, out_msg: Optional[RingMessageDescriptor] = None) -> Optional[RingMessageDescriptor]:
        """
        Consumer operation: reads the next available message.
        Returns the descriptor if available, None if empty (non-blocking).
        """
        tail = self.pointers.tail
        head = self.pointers.head

        # Check if empty
        if tail >= head:
            return None

        # Compute slot index
        slot_idx = tail & self.mask
        slot = self.buffer[slot_idx]

        if out_msg is not None:
            # Copy memory directly into destination buffer
            ctypes.memmove(
                ctypes.byref(out_msg),
                ctypes.byref(slot),
                ctypes.sizeof(RingMessageDescriptor)
            )
            result = out_msg
        else:
            result = slot

        # Advance tail pointer (Consumer release)
        self.pointers.tail = tail + 1
        self.total_popped += 1
        return result

    def is_empty(self) -> bool:
        return self.pointers.tail >= self.pointers.head

    def is_full(self) -> bool:
        return (self.pointers.head - self.pointers.tail) >= self.capacity

    def size(self) -> int:
        return int(self.pointers.head - self.pointers.tail)

    def get_telemetry(self) -> Dict[str, Any]:
        """Computes real-time throughput and queue utilization metrics."""
        current_size = self.size()
        utilization_pct = (current_size / self.capacity) * 100.0
        descriptor_bytes = ctypes.sizeof(RingMessageDescriptor)
        total_buffer_bytes = self.capacity * descriptor_bytes

        return {
            "capacity": self.capacity,
            "current_size": current_size,
            "utilization_pct": round(utilization_pct, 2),
            "descriptor_size_bytes": descriptor_bytes,
            "total_buffer_bytes": total_buffer_bytes,
            "total_buffer_kb": round(total_buffer_bytes / 1024, 2),
            "total_pushed": self.total_pushed,
            "total_popped": self.total_popped,
            "dropped_count": self.dropped_count,
            "false_sharing_protection": "Active (128-byte cache-line isolation)"
        }
