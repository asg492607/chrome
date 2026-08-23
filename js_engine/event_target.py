"""
DOM Event Dispatch Engine & Event Listener Registry.
Implements W3C 3-phase event propagation (capturing, target, bubbling),
event listener registration, event.stopPropagation(), event.preventDefault(), and ECS integration.
"""

import sys
import os
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Callable, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core_platform.ecs_memory import DocumentTreeMemoryBank, NodeFlags, NULL_ENTITY


class EventPhase(Enum):
    NONE = 0
    CAPTURING_PHASE = 1
    AT_TARGET = 2
    BUBBLING_PHASE = 3


class DOMEvent:
    """W3C Standard DOM Event representation."""

    def __init__(self, event_type: str, bubbles: bool = True, cancelable: bool = True):
        self.type = event_type.strip().lower()
        self.bubbles = bubbles
        self.cancelable = cancelable
        self.target_id: int = NULL_ENTITY
        self.current_target_id: int = NULL_ENTITY
        self.event_phase = EventPhase.NONE

        self.default_prevented: bool = False
        self.propagation_stopped: bool = False

    def stop_propagation(self) -> None:
        """Prevents further propagation of the current event in capturing and bubbling phases."""
        self.propagation_stopped = True

    def prevent_default(self) -> None:
        """Cancels the default action of the event if it is cancelable."""
        if self.cancelable:
            self.default_prevented = True

    def __repr__(self) -> str:
        return f"DOMEvent('{self.type}', phase={self.event_phase.name}, target={self.target_id})"


class EventListener:
    """Represents a registered DOM Event Listener wrapper."""

    def __init__(self, callback: Callable[[DOMEvent], None], use_capture: bool = False, once: bool = False):
        self.callback = callback
        self.use_capture = use_capture
        self.once = once


class EventListenerRegistry:
    """Registry mapping (entity_id, event_type) -> List[EventListener]."""

    def __init__(self):
        self.registry: Dict[Tuple[int, str], List[EventListener]] = {}
        self.total_listeners_count = 0

    def add_event_listener(
        self,
        entity_id: int,
        event_type: str,
        callback: Callable[[DOMEvent], None],
        use_capture: bool = False,
        once: bool = False
    ) -> None:
        """Registers an event listener callback for specified entity ID and event type."""
        key = (entity_id, event_type.strip().lower())
        if key not in self.registry:
            self.registry[key] = []

        # Prevent duplicate registration
        for existing in self.registry[key]:
            if existing.callback == callback and existing.use_capture == use_capture:
                return

        self.registry[key].append(EventListener(callback, use_capture, once))
        self.total_listeners_count += 1

    def remove_event_listener(
        self,
        entity_id: int,
        event_type: str,
        callback: Callable,
        use_capture: bool = False
    ) -> None:
        """Removes a registered event listener from target entity ID."""
        key = (entity_id, event_type.strip().lower())
        if key in self.registry:
            before_len = len(self.registry[key])
            self.registry[key] = [
                l for l in self.registry[key]
                if not (l.callback == callback and l.use_capture == use_capture)
            ]
            self.total_listeners_count -= (before_len - len(self.registry[key]))

    def get_listeners(self, entity_id: int, event_type: str, use_capture: bool) -> List[EventListener]:
        """Retrieves matching event listeners for specified phase (capture vs bubble)."""
        key = (entity_id, event_type.strip().lower())
        if key not in self.registry:
            return []
        return [l for l in self.registry[key] if l.use_capture == use_capture]

    def get_all_listeners(self, entity_id: int, event_type: str) -> List[EventListener]:
        """Retrieves all event listeners registered on target entity regardless of capture flag."""
        key = (entity_id, event_type.strip().lower())
        return self.registry.get(key, [])


class EventDispatchEngine:
    """W3C 3-Phase DOM Event Dispatch & Propagation Engine."""

    @classmethod
    def get_ancestor_chain(cls, bank: DocumentTreeMemoryBank, target_id: int) -> List[int]:
        """Constructs target ancestor chain [root_id, ..., parent_id, target_id] in O(D) time."""
        chain: List[int] = []
        visited = set()
        curr = target_id
        while curr != NULL_ENTITY and curr < bank.count and curr not in visited:
            visited.add(curr)
            chain.append(curr)
            p_id = bank.entities[curr].parent_index
            if p_id == curr:
                break
            curr = p_id
        chain.reverse()
        return chain


    @classmethod
    def dispatch_event(
        cls,
        bank: DocumentTreeMemoryBank,
        target_id: int,
        event: DOMEvent,
        registry: EventListenerRegistry
    ) -> bool:
        """
        Dispatches event across 3 W3C phases: Capturing -> At Target -> Bubbling.
        Returns True if event default action was NOT prevented, False otherwise.
        """
        if target_id >= bank.count:
            return True

        event.target_id = target_id
        chain = cls.get_ancestor_chain(bank, target_id)
        if not chain:
            return True

        # Phase 1: Capturing Phase (Root down to target's parent)
        event.event_phase = EventPhase.CAPTURING_PHASE
        for node_id in chain[:-1]:
            if event.propagation_stopped:
                break
            event.current_target_id = node_id
            listeners = registry.get_listeners(node_id, event.type, use_capture=True)
            for listener in list(listeners):
                listener.callback(event)
                if listener.once:
                    registry.remove_event_listener(node_id, event.type, listener.callback, use_capture=True)
                if event.propagation_stopped:
                    break

        # Phase 2: At Target (Target entity)
        if not event.propagation_stopped:
            event.event_phase = EventPhase.AT_TARGET
            event.current_target_id = target_id
            listeners = registry.get_all_listeners(target_id, event.type)
            for listener in list(listeners):
                listener.callback(event)
                if listener.once:
                    registry.remove_event_listener(target_id, event.type, listener.callback, use_capture=listener.use_capture)
                if event.propagation_stopped:
                    break

        # Phase 3: Bubbling Phase (Target's parent up to Root)
        if event.bubbles and not event.propagation_stopped:
            event.event_phase = EventPhase.BUBBLING_PHASE
            for node_id in reversed(chain[:-1]):
                if event.propagation_stopped:
                    break
                event.current_target_id = node_id
                listeners = registry.get_listeners(node_id, event.type, use_capture=False)
                for listener in list(listeners):
                    listener.callback(event)
                    if listener.once:
                        registry.remove_event_listener(node_id, event.type, listener.callback, use_capture=False)
                    if event.propagation_stopped:
                        break

        return not event.default_prevented
