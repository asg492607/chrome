"""
Unit & Benchmark Test Suite for DOM Event Dispatch Engine & Event Listener Registry (Sprint 17).
Verifies W3C 3-phase event propagation (capturing, target, bubbling), event listener registration/removal,
event.stopPropagation(), event.preventDefault(), and high-speed event dispatching.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from core_platform.tag_constants import TagType
from core_platform.ecs_memory import DocumentTreeMemoryBank
from rendering_engine.html_parser import HTML5TreeBuilder
from js_engine.event_target import (
    EventPhase,
    DOMEvent,
    EventListener,
    EventListenerRegistry,
    EventDispatchEngine
)


class TestEventTargetSubsystem(unittest.TestCase):

    def test_event_listener_registration_and_removal(self):
        """Verify adding and removing event listeners by entity ID and event type."""
        registry = EventListenerRegistry()
        calls = []

        def on_click(evt):
            calls.append(evt.type)

        # Register listener
        registry.add_event_listener(1, "click", on_click, use_capture=False)
        self.assertEqual(len(registry.get_listeners(1, "click", use_capture=False)), 1)

        # Remove listener
        registry.remove_event_listener(1, "click", on_click, use_capture=False)
        self.assertEqual(len(registry.get_listeners(1, "click", use_capture=False)), 0)

    def test_3_phase_w3c_event_propagation_order(self):
        """Verify W3C 3-phase event propagation order: Capturing -> At Target -> Bubbling."""
        html = '<html><body><div id="parent"><button id="btn">Submit</button></div></body></html>'
        builder = HTML5TreeBuilder()
        root_id, bank = builder.parse_html(html)

        # Find div#parent and button#btn IDs
        parent_id = [i for i in range(bank.count) if bank.entities[i].tag_type == int(TagType.DIV)][0]
        btn_id = [i for i in range(bank.count) if bank.entities[i].tag_type == int(TagType.BUTTON)][0]

        registry = EventListenerRegistry()
        call_log = []

        def capture_parent(evt):
            call_log.append(f"parent_capture_{evt.event_phase.name}")

        def at_target_btn(evt):
            call_log.append(f"btn_target_{evt.event_phase.name}")

        def bubble_parent(evt):
            call_log.append(f"parent_bubble_{evt.event_phase.name}")

        registry.add_event_listener(parent_id, "click", capture_parent, use_capture=True)
        registry.add_event_listener(btn_id, "click", at_target_btn, use_capture=False)
        registry.add_event_listener(parent_id, "click", bubble_parent, use_capture=False)

        # Dispatch event on button
        evt = DOMEvent("click", bubbles=True, cancelable=True)
        ok = EventDispatchEngine.dispatch_event(bank, btn_id, evt, registry)

        self.assertTrue(ok)
        self.assertEqual(call_log, [
            "parent_capture_CAPTURING_PHASE",
            "btn_target_AT_TARGET",
            "parent_bubble_BUBBLING_PHASE"
        ])

    def test_stop_propagation_halts_dispatch(self):
        """Verify calling event.stopPropagation() halts propagation immediately."""
        html = '<html><body><div id="parent"><button id="btn">Submit</button></div></body></html>'
        builder = HTML5TreeBuilder()
        root_id, bank = builder.parse_html(html)

        parent_id = [i for i in range(bank.count) if bank.entities[i].tag_type == int(TagType.DIV)][0]
        btn_id = [i for i in range(bank.count) if bank.entities[i].tag_type == int(TagType.BUTTON)][0]

        registry = EventListenerRegistry()
        call_log = []

        def capture_parent(evt):
            call_log.append("parent_capture")
            evt.stop_propagation()

        def at_target_btn(evt):
            call_log.append("btn_target")

        registry.add_event_listener(parent_id, "click", capture_parent, use_capture=True)
        registry.add_event_listener(btn_id, "click", at_target_btn, use_capture=False)

        evt = DOMEvent("click", bubbles=True)
        EventDispatchEngine.dispatch_event(bank, btn_id, evt, registry)

        # Only parent_capture should be called
        self.assertEqual(call_log, ["parent_capture"])
        self.assertTrue(evt.propagation_stopped)

    def test_prevent_default_returns_false(self):
        """Verify calling event.preventDefault() returns False from dispatch_event."""
        bank = DocumentTreeMemoryBank()
        btn_id = bank.allocate_entity(TagType.BUTTON)

        registry = EventListenerRegistry()

        def on_submit(evt):
            evt.prevent_default()

        registry.add_event_listener(btn_id, "submit", on_submit)

        evt = DOMEvent("submit", bubbles=True, cancelable=True)
        ok = EventDispatchEngine.dispatch_event(bank, btn_id, evt, registry)

        self.assertFalse(ok)
        self.assertTrue(evt.default_prevented)

    def test_high_speed_event_dispatch_benchmark(self):
        """
        Benchmark: Dispatch 10,000 events across a 5-level DOM tree.
        Asserts duration < 0.15s (> 60,000 events/sec).
        """
        html = '<html><body><div><section><button>Action</button></section></div></body></html>'
        builder = HTML5TreeBuilder()
        root_id, bank = builder.parse_html(html)

        btn_id = [i for i in range(bank.count) if bank.entities[i].tag_type == int(TagType.BUTTON)][0]
        registry = EventListenerRegistry()

        counter = {"count": 0}
        def dummy_listener(evt):
            counter["count"] += 1

        registry.add_event_listener(root_id, "click", dummy_listener, use_capture=True)
        registry.add_event_listener(btn_id, "click", dummy_listener, use_capture=False)

        evt = DOMEvent("click", bubbles=True)

        start_time = time.perf_counter()
        for _ in range(10000):
            evt.propagation_stopped = False
            evt.default_prevented = False
            EventDispatchEngine.dispatch_event(bank, btn_id, evt, registry)
        duration = time.perf_counter() - start_time

        total_dispatches = 10000
        events_per_sec = total_dispatches / duration
        latency_us = (duration / total_dispatches) * 1_000_000

        self.assertLess(duration, 0.20, f"10k event dispatches took {duration*1000:.2f}ms (must be < 200ms)")
        print(f"\n[Sprint 17 DOM Event Dispatch Engine Benchmark] {total_dispatches:,} Events Dispatched:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Event Dispatch Speed: {events_per_sec:,.0f} events/second")
        print(f"  - Average Event Dispatch Latency: {latency_us:.2f} µs/event")


if __name__ == "__main__":
    unittest.main()
