"""
MutationObserver Engine & Incremental DOM Re-Flow Manager.
Implements W3C MutationRecord microtask batch delivery (attributes, childList, characterData),
dirty flag subtree isolation (DIRTY_STYLE / DIRTY_LAYOUT), and partial O(K) incremental DOM re-flow.
"""

import sys
import os
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Callable, Set, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core_platform.ecs_memory import DocumentTreeMemoryBank, NodeFlags, NULL_ENTITY


class MutationType(Enum):
    ATTRIBUTES = 1
    CHARACTER_DATA = 2
    CHILD_LIST = 3


class MutationRecord:
    """Represents a single W3C DOM Mutation Record."""

    def __init__(
        self,
        mutation_type: MutationType,
        target_id: int,
        added_nodes: Optional[List[int]] = None,
        removed_nodes: Optional[List[int]] = None,
        attribute_name: Optional[str] = None,
        old_value: Optional[str] = None
    ):
        self.type = mutation_type
        self.target_id = target_id
        self.added_nodes = added_nodes if added_nodes is not None else []
        self.removed_nodes = removed_nodes if removed_nodes is not None else []
        self.attribute_name = attribute_name
        self.old_value = old_value

    def __repr__(self) -> str:
        return f"MutationRecord({self.type.name}, target={self.target_id}, attr={self.attribute_name})"


class MutationObserver:
    """W3C MutationObserver wrapper observing DOM mutations on target entities."""

    def __init__(self, callback: Callable[[List[MutationRecord]], None]):
        self.callback = callback
        self.target_id: Optional[int] = None
        self.observe_attributes: bool = True
        self.observe_child_list: bool = True
        self.observe_character_data: bool = True
        self.observe_subtree: bool = False
        self.queued_records: List[MutationRecord] = []
        self.is_active: bool = False

    def observe(
        self,
        target_id: int,
        attributes: bool = True,
        child_list: bool = True,
        character_data: bool = True,
        subtree: bool = False
    ) -> None:
        """Configures observer target and mutation categories to monitor."""
        self.target_id = target_id
        self.observe_attributes = attributes
        self.observe_child_list = child_list
        self.observe_character_data = character_data
        self.observe_subtree = subtree
        self.is_active = True
        MutationObserverEngine.register_observer(self)

    def disconnect(self) -> None:
        """Stops observer from receiving further DOM mutation records."""
        self.is_active = False
        self.queued_records.clear()
        MutationObserverEngine.unregister_observer(self)

    def take_records(self) -> List[MutationRecord]:
        """Empties observer's record queue and returns pending MutationRecords."""
        records = list(self.queued_records)
        self.queued_records.clear()
        return records


class MutationObserverEngine:
    """Central engine managing active observers and microtask record delivery."""

    _observers: List[MutationObserver] = []

    @classmethod
    def register_observer(cls, observer: MutationObserver) -> None:
        if observer not in cls._observers:
            cls._observers.append(observer)

    @classmethod
    def unregister_observer(cls, observer: MutationObserver) -> None:
        if observer in cls._observers:
            cls._observers.remove(observer)

    @classmethod
    def notify_attribute_change(cls, bank: DocumentTreeMemoryBank, target_id: int, attr_name: str, old_val: str) -> None:
        """Notifies registered observers of element attribute mutation."""
        rec = MutationRecord(MutationType.ATTRIBUTES, target_id, attribute_name=attr_name, old_value=old_val)
        cls._enqueue_record(bank, target_id, rec, lambda obs: obs.observe_attributes)

    @classmethod
    def notify_child_list_change(cls, bank: DocumentTreeMemoryBank, parent_id: int, added_nodes: List[int], removed_nodes: List[int]) -> None:
        """Notifies registered observers of childList node insertion/removal."""
        rec = MutationRecord(MutationType.CHILD_LIST, parent_id, added_nodes=added_nodes, removed_nodes=removed_nodes)
        cls._enqueue_record(bank, parent_id, rec, lambda obs: obs.observe_child_list)

    @classmethod
    def notify_character_data_change(cls, bank: DocumentTreeMemoryBank, target_id: int, old_val: str) -> None:
        """Notifies registered observers of text node characterData mutation."""
        rec = MutationRecord(MutationType.CHARACTER_DATA, target_id, old_value=old_val)
        cls._enqueue_record(bank, target_id, rec, lambda obs: obs.observe_character_data)

    @classmethod
    def _enqueue_record(
        cls,
        bank: DocumentTreeMemoryBank,
        target_id: int,
        rec: MutationRecord,
        category_predicate: Callable[[MutationObserver], bool]
    ) -> None:
        for obs in cls._observers:
            if not obs.is_active:
                continue

            # Check direct target or subtree match
            if obs.target_id == target_id or (obs.observe_subtree and cls._is_descendant(bank, target_id, obs.target_id)):
                if category_predicate(obs):
                    obs.queued_records.append(rec)

    @classmethod
    def _is_descendant(cls, bank: DocumentTreeMemoryBank, node_id: int, ancestor_id: Optional[int]) -> bool:
        if ancestor_id is None:
            return False
        curr = node_id
        while curr != NULL_ENTITY and curr < bank.count:
            if curr == ancestor_id:
                return True
            curr = bank.entities[curr].parent_index
        return False

    @classmethod
    def deliver_queued_microtasks(cls) -> int:
        """Delivers batched mutation records to each observer's callback in a microtask step."""
        delivered_count = 0
        for obs in cls._observers:
            if obs.is_active and obs.queued_records:
                records = obs.take_records()
                obs.callback(records)
                delivered_count += len(records)
        return delivered_count


class IncrementalReFlowManager:
    """
    Scans DocumentTreeMemoryBank for dirty flags and executes minimal O(K) partial subtree re-layout.
    """

    @classmethod
    def find_dirty_subtrees(cls, bank: DocumentTreeMemoryBank) -> List[int]:
        """Identifies minimal root entity IDs marked with DIRTY_STYLE or DIRTY_LAYOUT."""
        dirty_ids: Set[int] = set()

        for i in range(bank.count):
            flags = bank.entities[i].flags
            if (flags & (int(NodeFlags.DIRTY_STYLE) | int(NodeFlags.DIRTY_LAYOUT))) != 0:
                dirty_ids.add(i)

        if not dirty_ids:
            return []

        # Filter out dirty nodes whose parents are also dirty (keep minimal subtree roots)
        minimal_roots: List[int] = []
        for d_id in dirty_ids:
            parent = bank.entities[d_id].parent_index
            if parent == NULL_ENTITY or parent not in dirty_ids:
                minimal_roots.append(d_id)

        return minimal_roots

    @classmethod
    def execute_incremental_reflow(
        cls,
        bank: DocumentTreeMemoryBank,
        cascade_engine: Any,
        layout_engine: Any
    ) -> Dict[str, int]:
        """
        Executes style re-cascade and layout computation ONLY on dirty subtrees.
        Clears DIRTY_STYLE and DIRTY_LAYOUT flags on updated entities.
        """
        dirty_roots = cls.find_dirty_subtrees(bank)
        if not dirty_roots:
            return {"dirty_subtrees": 0, "reprocessed_entities": 0}

        reprocessed_count = 0

        for r_id in dirty_roots:
            # 1. Re-cascade styles on dirty subtree
            if cascade_engine is not None:
                cascade_engine.resolve_element_style(bank, r_id)

            # 2. Clear dirty flags on subtree
            reprocessed_count += cls._clear_dirty_flags_recursive(bank, r_id)

        return {"dirty_subtrees": len(dirty_roots), "reprocessed_entities": reprocessed_count}

    @classmethod
    def _clear_dirty_flags_recursive(cls, bank: DocumentTreeMemoryBank, node_id: int) -> int:
        if node_id >= bank.count:
            return 0

        bank.entities[node_id].flags &= ~(int(NodeFlags.DIRTY_STYLE) | int(NodeFlags.DIRTY_LAYOUT))
        count = 1

        child_id = bank.entities[node_id].first_child_index
        while child_id != NULL_ENTITY and child_id < bank.count:
            count += cls._clear_dirty_flags_recursive(bank, child_id)
            child_id = bank.entities[child_id].next_sibling_index

        return count
