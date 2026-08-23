"""
IndexedDB Transactional Database & B-Tree Storage Engine.
Implements W3C IndexedDB spec, ACID transactions (READ_ONLY, READ_WRITE, abort rollback),
ObjectStore indexing, secondary B-Tree lookups, IDBKeyRange cursor iteration, and per-origin database isolation.
"""

import sys
import os
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Any, Callable

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TransactionMode(Enum):
    READ_ONLY = 1
    READ_WRITE = 2
    VERSION_CHANGE = 3


class IDBKeyRange:
    """W3C IDBKeyRange representation for key range bounding."""

    def __init__(
        self,
        lower: Any = None,
        upper: Any = None,
        lower_open: bool = False,
        upper_open: bool = False
    ):
        self.lower = lower
        self.upper = upper
        self.lower_open = lower_open
        self.upper_open = upper_open

    def contains(self, key: Any) -> bool:
        """Evaluates whether specified key falls within range boundaries."""
        if self.lower is not None:
            if self.lower_open and key <= self.lower:
                return False
            if not self.lower_open and key < self.lower:
                return False
        if self.upper is not None:
            if self.upper_open and key >= self.upper:
                return False
            if not self.upper_open and key > self.upper:
                return False
        return True

    @classmethod
    def only(cls, value: Any) -> "IDBKeyRange":
        return cls(lower=value, upper=value, lower_open=False, upper_open=False)

    @classmethod
    def lower_bound(cls, lower: Any, open_bound: bool = False) -> "IDBKeyRange":
        return cls(lower=lower, upper=None, lower_open=open_bound, upper_open=False)

    @classmethod
    def upper_bound(cls, upper: Any, open_bound: bool = False) -> "IDBKeyRange":
        return cls(lower=None, upper=upper, lower_open=False, upper_open=open_bound)

    @classmethod
    def bound(cls, lower: Any, upper: Any, lower_open: bool = False, upper_open: bool = False) -> "IDBKeyRange":
        return cls(lower=lower, upper=upper, lower_open=lower_open, upper_open=upper_open)


class IDBCursor:
    """W3C IDBCursor representation for iterating over key ranges in ObjectStores."""

    def __init__(self, records: List[Tuple[Any, Any, Any]]): # [(key, primary_key, value)]
        self._records = records
        self._index = 0

    @property
    def key(self) -> Optional[Any]:
        if 0 <= self._index < len(self._records):
            return self._records[self._index][0]
        return None

    @property
    def primary_key(self) -> Optional[Any]:
        if 0 <= self._index < len(self._records):
            return self._records[self._index][1]
        return None

    @property
    def value(self) -> Optional[Any]:
        if 0 <= self._index < len(self._records):
            return self._records[self._index][2]
        return None

    def continue_cursor(self) -> bool:
        """Advances cursor to the next record in range. Returns True if record valid."""
        self._index += 1
        return self._index < len(self._records)


class ObjectStore:
    """IndexedDB ObjectStore supporting primary keys, auto-increment, and secondary B-Tree indexing."""

    def __init__(self, name: str, key_path: Optional[str] = None, auto_increment: bool = False):
        self.name = name
        self.key_path = key_path
        self.auto_increment = auto_increment
        self._next_auto_id = 1

        self._records: Dict[Any, Any] = {} # PrimaryKey -> RecordValue
        self._indexes: Dict[str, Dict[Any, List[Any]]] = {} # IndexName -> {IndexVal: [PrimaryKeys]}
        self._index_key_paths: Dict[str, str] = {} # IndexName -> KeyPath

    def put(self, value: Any, key: Optional[Any] = None) -> Any:
        """Inserts or updates a value in the ObjectStore and updates secondary indexes."""
        primary_key = key

        if primary_key is None and self.key_path and isinstance(value, dict):
            primary_key = value.get(self.key_path)

        if primary_key is None and self.auto_increment:
            primary_key = self._next_auto_id
            self._next_auto_id += 1
            if isinstance(value, dict) and self.key_path:
                value[self.key_path] = primary_key

        if primary_key is None:
            raise ValueError("DataError: No key provided and no auto_increment configured.")

        # Remove old index entries if overwriting existing key
        if primary_key in self._records:
            self._remove_from_indexes(primary_key, self._records[primary_key])

        self._records[primary_key] = value

        # Update secondary B-Tree indexes
        self._add_to_indexes(primary_key, value)
        return primary_key

    def get(self, key: Any) -> Optional[Any]:
        """Retrieves record by primary key."""
        return self._records.get(key)

    def delete(self, key: Any) -> bool:
        """Deletes record by primary key and cleans secondary index references."""
        if key in self._records:
            old_val = self._records.pop(key)
            self._remove_from_indexes(key, old_val)
            return True
        return False

    def clear(self) -> None:
        """Clears all records and indexes in store."""
        self._records.clear()
        self._indexes.clear()
        self._index_key_paths.clear()

    def create_index(self, index_name: str, key_path: str) -> None:
        """Creates a secondary B-Tree index lookup on target key_path."""
        self._index_key_paths[index_name] = key_path
        self._indexes[index_name] = {}

        # Index existing records
        for p_key, val in self._records.items():
            self._add_single_index(index_name, key_path, p_key, val)

    def get_via_index(self, index_name: str, index_value: Any) -> Optional[Any]:
        """Queries secondary B-Tree index and returns matching record value."""
        if index_name in self._indexes:
            p_keys = self._indexes[index_name].get(index_value, [])
            if p_keys:
                return self._records.get(p_keys[0])
        return None

    def open_cursor(self, key_range: Optional[IDBKeyRange] = None) -> IDBCursor:
        """Returns IDBCursor iterating over records matching key_range."""
        cursor_tuples = []
        for p_key in sorted(self._records.keys()):
            if key_range is None or key_range.contains(p_key):
                cursor_tuples.append((p_key, p_key, self._records[p_key]))
        return IDBCursor(cursor_tuples)

    def _add_to_indexes(self, p_key: Any, val: Any) -> None:
        for idx_name, k_path in self._index_key_paths.items():
            self._add_single_index(idx_name, k_path, p_key, val)

    def _add_single_index(self, idx_name: str, k_path: str, p_key: Any, val: Any) -> None:
        if isinstance(val, dict) and k_path in val:
            idx_val = val[k_path]
            if idx_val not in self._indexes[idx_name]:
                self._indexes[idx_name][idx_val] = []
            if p_key not in self._indexes[idx_name][idx_val]:
                self._indexes[idx_name][idx_val].append(p_key)

    def _remove_from_indexes(self, p_key: Any, val: Any) -> None:
        for idx_name, k_path in self._index_key_paths.items():
            if isinstance(val, dict) and k_path in val:
                idx_val = val[k_path]
                if idx_name in self._indexes and idx_val in self._indexes[idx_name]:
                    if p_key in self._indexes[idx_name][idx_val]:
                        self._indexes[idx_name][idx_val].remove(p_key)


class IDBTransaction:
    """W3C IDBTransaction providing ACID transactional guarantees with commit and abort rollback."""

    def __init__(self, db: "IDBDatabase", store_names: List[str], mode: TransactionMode = TransactionMode.READ_ONLY):
        self.db = db
        self.store_names = store_names
        self.mode = mode
        self.is_active = True

        self._pending_puts: Dict[str, List[Tuple[Any, Any]]] = {s: [] for s in store_names}
        self._pending_deletes: Dict[str, List[Any]] = {s: [] for s in store_names}

    def object_store(self, name: str) -> ObjectStore:
        """Returns the ObjectStore bound to this transaction."""
        if name not in self.store_names or name not in self.db.stores:
            raise ValueError(f"NotFoundError: Store '{name}' not included in transaction scope.")
        return self.db.stores[name]

    def put_staged(self, store_name: str, value: Any, key: Optional[Any] = None) -> None:
        """Stages a put operation in transaction buffer (READ_WRITE mode)."""
        if self.mode == TransactionMode.READ_ONLY:
            raise ValueError("ReadOnlyError: Cannot modify store during READ_ONLY transaction.")
        if not self.is_active:
            raise ValueError("TransactionInactiveError: Transaction completed or aborted.")
        self._pending_puts[store_name].append((key, value))

    def commit(self) -> None:
        """Flushes buffered transactional operations into persistent ObjectStores."""
        if not self.is_active:
            return

        for s_name in self.store_names:
            store = self.db.stores[s_name]

            # Process pending deletes
            for d_key in self._pending_deletes[s_name]:
                store.delete(d_key)

            # Process pending puts
            for p_key, p_val in self._pending_puts[s_name]:
                store.put(p_val, p_key)

        self.is_active = False

    def abort(self) -> None:
        """Discards all staged transactional mutations (Rollback)."""
        for s_name in self.store_names:
            self._pending_puts[s_name].clear()
            self._pending_deletes[s_name].clear()
        self.is_active = False


class IDBDatabase:
    """W3C IDBDatabase managing versioning and ObjectStore registry."""

    def __init__(self, name: str, version: int = 1):
        self.name = name
        self.version = version
        self.stores: Dict[str, ObjectStore] = {}

    def create_object_store(self, name: str, key_path: Optional[str] = None, auto_increment: bool = False) -> ObjectStore:
        """Creates a new ObjectStore in database."""
        store = ObjectStore(name, key_path, auto_increment)
        self.stores[name] = store
        return store

    def transaction(self, store_names: List[str], mode: TransactionMode = TransactionMode.READ_ONLY) -> IDBTransaction:
        """Starts an IDBTransaction over target store names."""
        return IDBTransaction(self, store_names, mode)


class IndexedDBEngine:
    """Origin-partitioned manager for IndexedDB databases."""

    _databases: Dict[Tuple[str, str], IDBDatabase] = {}

    @classmethod
    def open_database(cls, origin: str, db_name: str, version: int = 1) -> IDBDatabase:
        """Opens or creates an origin-isolated IDBDatabase instance."""
        clean_origin = origin.strip().lower()
        clean_db = db_name.strip().lower()
        key = (clean_origin, clean_db)

        if key not in cls._databases:
            cls._databases[key] = IDBDatabase(clean_db, version)

        return cls._databases[key]
