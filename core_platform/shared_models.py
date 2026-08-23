"""
Shared models for the PacketForge platform.
"""

from core_platform.tag_constants import TagType, NodeFlags, TAG_NAME_TO_TYPE, TAG_TYPE_TO_NAME
from core_platform.ecs_memory import (
    Rect4f,
    DOMEntity32,
    DocumentTreeMemoryBank,
    NULL_ENTITY
)
from core_platform.lockfree_ring_buffer import (
    RingMessageDescriptor,
    SPSCAtomicPointers,
    LockFreeRingBuffer
)

class NetworkPacket:
    def __init__(self, source, destination, payload):
        self.source = source
        self.destination = destination
        self.payload = payload


