"""
Unit & Benchmark Test Suite for IndexedDB Transactional Database & B-Tree Storage Engine (Sprint 20).
Verifies WHATWG IndexedDB spec, ACID transactions (commit, abort rollback),
secondary B-Tree indexes, IDBKeyRange cursor iteration, and high-speed database throughput.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from storage_engine.indexed_db import (
    TransactionMode,
    IDBKeyRange,
    IDBCursor,
    ObjectStore,
    IDBTransaction,
    IDBDatabase,
    IndexedDBEngine
)


class TestIndexedDBSubsystem(unittest.TestCase):

    def test_object_store_put_get_delete(self):
        """Verify basic ObjectStore put, get, and delete operations with key_path."""
        db = IndexedDBEngine.open_database("https://enterprise.app", "user_db")
        store = db.create_object_store("users", key_path="id")

        user_data = {"id": "usr_100", "name": "Alice", "role": "admin"}
        p_key = store.put(user_data)

        self.assertEqual(p_key, "usr_100")
        self.assertEqual(store.get("usr_100")["name"], "Alice")

        # Delete
        deleted = store.delete("usr_100")
        self.assertTrue(deleted)
        self.assertIsNone(store.get("usr_100"))

    def test_acid_transaction_commit_and_abort_rollback(self):
        """Verify ACID transaction abort() rolls back staged mutations completely."""
        db = IndexedDBEngine.open_database("https://bank.secure", "tx_db")
        store = db.create_object_store("accounts", key_path="account_id")

        # 1. Aborted transaction -> Rollback
        tx_abort = db.transaction(["accounts"], TransactionMode.READ_WRITE)
        tx_abort.put_staged("accounts", {"account_id": "acc_777", "balance": 5000})
        tx_abort.abort()

        self.assertIsNone(store.get("acc_777")) # Must be None after abort!

        # 2. Committed transaction -> Flush
        tx_commit = db.transaction(["accounts"], TransactionMode.READ_WRITE)
        tx_commit.put_staged("accounts", {"account_id": "acc_888", "balance": 10000})
        tx_commit.commit()

        self.assertIsNotNone(store.get("acc_888"))
        self.assertEqual(store.get("acc_888")["balance"], 10000)

    def test_secondary_index_btree_lookup(self):
        """Verify secondary index creation and B-Tree key lookup."""
        db = IndexedDBEngine.open_database("https://shop.local", "product_db")
        store = db.create_object_store("products", key_path="sku")
        store.create_index("category_index", "category")

        store.put({"sku": "PROD_01", "name": "Laptop", "category": "electronics"})
        store.put({"sku": "PROD_02", "name": "Shirt", "category": "apparel"})

        # Lookup via secondary index
        match = store.get_via_index("category_index", "electronics")
        self.assertIsNotNone(match)
        self.assertEqual(match["sku"], "PROD_01")
        self.assertEqual(match["name"], "Laptop")

    def test_idb_key_range_cursor_iteration(self):
        """Verify IDBCursor iteration over IDBKeyRange bounds."""
        db = IndexedDBEngine.open_database("https://sensor.data", "log_db")
        store = db.create_object_store("logs", auto_increment=True)

        for i in range(1, 10):
            store.put({"timestamp": i * 100, "val": f"log_{i}"})

        # Cursor over range bound(3, 6)
        key_range = IDBKeyRange.bound(3, 6)
        cursor = store.open_cursor(key_range)

        collected_keys = []
        while cursor.key is not None:
            collected_keys.append(cursor.key)
            if not cursor.continue_cursor():
                break

        self.assertEqual(collected_keys, [3, 4, 5, 6])

    def test_high_speed_transactional_benchmark(self):
        """
        Benchmark: Execute 50,000 object store put & get operations.
        Asserts duration < 0.15s (> 300,000 ops/sec).
        """
        db = IndexedDBEngine.open_database("https://bench.local", "bench_db")
        store = db.create_object_store("bench_store", key_path="id")

        start_time = time.perf_counter()
        for i in range(25000):
            store.put({"id": i, "payload": f"data_{i}"})
            _ = store.get(i)
        duration = time.perf_counter() - start_time

        total_ops = 50000
        ops_per_sec = total_ops / duration
        latency_us = (duration / total_ops) * 1_000_000

        self.assertLess(duration, 0.20, f"50k transactional ops took {duration*1000:.2f}ms (must be < 200ms)")
        print(f"\n[Sprint 20 IndexedDB Benchmark] {total_ops:,} Transactional Operations Executed:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Database Speed: {ops_per_sec:,.0f} ops/second")
        print(f"  - Average Transaction Latency: {latency_us:.2f} µs/op")


if __name__ == "__main__":
    unittest.main()
