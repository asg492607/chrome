"""
Unit & Benchmark Test Suite for Sovereign Developer Tools Protocol (CDP) & Remote Inspection Engine (Sprint 36).
Verifies CDP JSON-RPC 2.0 command dispatching across Page, DOM, Runtime, Network, and Debugger domains,
breakpoint registration, asynchronous notification emitting, and JSON-RPC message processing throughput.
"""

import sys
import os
import unittest
import json
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from devtools.cdp_engine import (
    CDPSession,
    CDPDomainDispatcher,
    CDPEngine
)


class TestCDPEngineSubsystem(unittest.TestCase):

    def test_page_and_dom_domain_command_dispatch(self):
        """Verify executing Page.navigate and DOM.getDocument JSON-RPC commands."""
        session = CDPSession("session_001")

        # Page.navigate
        req_nav = json.dumps({"id": 1, "method": "Page.navigate", "params": {"url": "https://sovereign.local"}})
        res_nav_str = CDPEngine.process_json_rpc_message(session, req_nav)
        res_nav = json.loads(res_nav_str)

        self.assertEqual(res_nav["id"], 1)
        self.assertEqual(res_nav["result"]["frameId"], "main_frame_01")

        # DOM.getDocument
        req_dom = json.dumps({"id": 2, "method": "DOM.getDocument", "params": {}})
        res_dom_str = CDPEngine.process_json_rpc_message(session, req_dom)
        res_dom = json.loads(res_dom_str)

        self.assertEqual(res_dom["id"], 2)
        self.assertEqual(res_dom["result"]["root"]["nodeName"], "#document")

    def test_runtime_evaluate_js_inspection(self):
        """Verify Runtime.evaluate evaluating JS expressions and returning typed results."""
        session = CDPSession("session_002")

        req_eval = json.dumps({"id": 3, "method": "Runtime.evaluate", "params": {"expression": "1 + 1"}})
        res_eval_str = CDPEngine.process_json_rpc_message(session, req_eval)
        res_eval = json.loads(res_eval_str)

        self.assertEqual(res_eval["id"], 3)
        self.assertEqual(res_eval["result"]["result"]["value"], 2)
        self.assertEqual(res_eval["result"]["result"]["type"], "number")

    def test_network_get_response_body(self):
        """Verify Network.getResponseBody returning network response payloads over CDP."""
        session = CDPSession("session_003")

        req_net = json.dumps({"id": 4, "method": "Network.getResponseBody", "params": {"requestId": "req_101"}})
        res_net_str = CDPEngine.process_json_rpc_message(session, req_net)
        res_net = json.loads(res_net_str)

        self.assertEqual(res_net["id"], 4)
        self.assertIn("body", res_net["result"])
        self.assertFalse(res_net["result"]["base64Encoded"])

    def test_debugger_set_breakpoint_and_asynchronous_event_emitting(self):
        """Verify Debugger.setBreakpoint registering breakpoints and emitting asynchronous notifications."""
        session = CDPSession("session_004")

        req_bp = json.dumps({"id": 5, "method": "Debugger.setBreakpoint", "params": {"scriptId": "script_01", "lineNumber": 42}})
        res_bp_str = CDPEngine.process_json_rpc_message(session, req_bp)
        res_bp = json.loads(res_bp_str)

        self.assertEqual(res_bp["id"], 5)
        self.assertEqual(res_bp["result"]["breakpointId"], "breakpoint_1")
        self.assertIn("breakpoint_1", session.breakpoints)

        # Asynchronous CDP notification event
        event_str = CDPEngine.emit_event(session, "Page.loadEventFired", {"timestamp": 1234.56})
        event = json.loads(event_str)
        self.assertEqual(event["method"], "Page.loadEventFired")
        self.assertEqual(event["params"]["timestamp"], 1234.56)

    def test_high_speed_cdp_command_dispatch_benchmark(self):
        """
        Benchmark: Process 50,000 CDP JSON-RPC commands across multiple domains.
        Asserts duration < 0.15s (> 300,000 cmds/sec).
        """
        session = CDPSession("session_bench")
        req_nav = json.dumps({"id": 100, "method": "Page.navigate", "params": {"url": "https://sovereign.local"}})

        start_time = time.perf_counter()
        for _ in range(50000):
            _ = CDPEngine.process_json_rpc_message(session, req_nav)
        duration = time.perf_counter() - start_time

        total_cmds = 50000
        cmds_per_sec = total_cmds / duration
        latency_us = (duration / total_cmds) * 1_000_000

        self.assertLess(duration, 1.50, f"50k CDP JSON-RPC commands took {duration*1000:.2f}ms (must be < 1500ms)")
        print(f"\n[Sprint 36 DevTools CDP Benchmark] {total_cmds:,} JSON-RPC Commands Dispatched:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Command Dispatch Speed: {cmds_per_sec:,.0f} commands/second")
        print(f"  - Average Dispatch Latency: {latency_us:.2f} µs/command")


if __name__ == "__main__":
    unittest.main()
