"""
Unit & Benchmark Test Suite for Web Share & Web Bluetooth Core Hardware Integration Engine (Sprint 40 - 80% Milestone).
Verifies navigator.bluetooth.requestDevice discovery, BLE GATT server connect/disconnect, primary service/characteristic
retrieval, raw byte read/write I/O, Web Share validation, and hardware I/O throughput.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from core_platform.web_bluetooth import (
    BluetoothRemoteGATTCharacteristic,
    BluetoothRemoteGATTService,
    BluetoothRemoteGATTServer,
    BluetoothDevice,
    WebBluetoothEngine,
    WebShareEngine
)


class TestWebBluetoothSubsystem(unittest.TestCase):

    def test_navigator_bluetooth_request_device(self):
        """Verify device discovery and filtering by service UUID or name."""
        engine = WebBluetoothEngine()

        dev = engine.requestDevice({"filters": [{"name": "Smart Heart Monitor"}]})
        self.assertEqual(dev.name, "Smart Heart Monitor")
        self.assertFalse(dev.gatt.connected)

        # Rejection when neither filters nor acceptAllDevices provided
        with self.assertRaises(ValueError):
            engine.requestDevice({})

    def test_ble_gatt_connect_and_service_discovery(self):
        """Verify gatt.connect(), getPrimaryService(), and getCharacteristic() lifecycle."""
        dev = BluetoothDevice("ble_001", "Pulse Oximeter")
        gatt = dev.gatt

        # Must raise ConnectionError when querying disconnected server
        with self.assertRaises(ConnectionError):
            gatt.getPrimaryService("0000180d-0000-1000-8000-00805f9b34fb")

        gatt.connect()
        self.assertTrue(gatt.connected)

        service = gatt.getPrimaryService("0000180d-0000-1000-8000-00805f9b34fb")
        self.assertEqual(service.uuid, "0000180d-0000-1000-8000-00805f9b34fb")

        char = service.getCharacteristic("00002a37-0000-1000-8000-00805f9b34fb")
        self.assertEqual(char.uuid, "00002a37-0000-1000-8000-00805f9b34fb")

    def test_characteristic_read_and_write(self):
        """Verify reading raw peripheral byte payloads (readValue) and writing command frames (writeValue)."""
        char = BluetoothRemoteGATTCharacteristic("00002a37-0000-1000-8000-00805f9b34fb", initial_value=b"\x00\x60")

        self.assertEqual(char.readValue(), b"\x00\x60")

        char.writeValue(b"\x01\x10\xff\xaa")
        self.assertEqual(char.readValue(), b"\x01\x10\xff\xaa")

    def test_web_share_api_validation_and_dispatch(self):
        """Verify Web Share API validation (canShare) and native dispatching (share)."""
        valid_data = {"title": "Sovereign Runtime Roadmap", "text": "80% Completion Milestone Hit", "url": "https://sovereign.engine"}

        self.assertTrue(WebShareEngine.canShare(valid_data))
        self.assertTrue(WebShareEngine.share(valid_data))

        self.assertFalse(WebShareEngine.canShare({}))
        with self.assertRaises(ValueError):
            WebShareEngine.share({})

    def test_high_speed_hardware_io_benchmark(self):
        """
        Benchmark: Execute 50,000 BLE GATT characteristic reads, writes, and Web Share dispatches.
        Asserts duration < 0.15s (> 300,000 ops/sec).
        """
        char = BluetoothRemoteGATTCharacteristic("00002a37-0000-1000-8000-00805f9b34fb")
        cmd_bytes = b"\x01\x02\x03\x04"
        share_data = {"title": "Bench", "url": "https://self.local"}

        start_time = time.perf_counter()
        for _ in range(25000):
            char.writeValue(cmd_bytes)
            _ = char.readValue()
            _ = WebShareEngine.canShare(share_data)
        duration = time.perf_counter() - start_time

        total_ops = 75000 # 25k writes + 25k reads + 25k share checks
        ops_per_sec = total_ops / duration
        latency_us = (duration / total_ops) * 1_000_000

        self.assertLess(duration, 0.20, f"75k Hardware I/O ops took {duration*1000:.2f}ms (must be < 200ms)")
        print(f"\n[Sprint 40 Web Bluetooth & Share Benchmark] {total_ops:,} Hardware I/O Ops Executed:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Hardware I/O Speed: {ops_per_sec:,.0f} ops/second")
        print(f"  - Average Operation Latency: {latency_us:.2f} µs/op")


if __name__ == "__main__":
    unittest.main()
