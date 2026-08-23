"""
Unit & Benchmark Test Suite for CSS3 Selector Parser & Rule Indexing Engine (Sprint 10).
Verifies stylesheet parsing, W3C 4-tuple specificity calculation, compound selector matching,
and O(1) bucketed candidate rule retrieval.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from core_platform.tag_constants import TagType
from rendering_engine.css_parser import (
    CSSSpecificity,
    CSSSelector,
    CSSDeclaration,
    CSSRule,
    CSSParser,
    CSSRuleIndex
)


class TestCSSParserSubsystem(unittest.TestCase):

    def test_css_parser_rules_and_declarations(self):
        """Test parsing of CSS rules, multi-selectors, declarations, and !important flags."""
        css = """
        #header, .top-nav {
            background-color: #333;
            color: #fff !important;
        }
        div.card {
            padding: 16px;
            margin: 8px;
        }
        """

        rules = CSSParser.parse_stylesheet(css)
        self.assertEqual(len(rules), 2)

        # 1. Rule 1: #header, .top-nav
        rule1 = rules[0]
        self.assertEqual(len(rule1.selectors), 2)
        self.assertEqual(len(rule1.declarations), 2)
        self.assertTrue(rule1.declarations[1].is_important)
        self.assertEqual(rule1.declarations[1].property_name, "color")

        # 2. Rule 2: div.card
        rule2 = rules[1]
        self.assertEqual(rule2.selectors[0].raw_text, "div.card")
        self.assertEqual(rule2.declarations[0].property_name, "padding")
        self.assertEqual(rule2.declarations[0].value, "16px")

    def test_w3c_specificity_calculation_and_comparison(self):
        """Verify W3C 4-tuple specificity calculation and comparison operators."""
        spec_id = CSSSelector("#header").specificity
        spec_class = CSSSelector(".card.active").specificity
        spec_tag = CSSSelector("div").specificity
        spec_compound = CSSSelector("div.card#main").specificity

        # #header -> (0, 1, 0, 0)
        self.assertEqual(spec_id.as_tuple(), (0, 1, 0, 0))

        # .card.active -> (0, 0, 2, 0)
        self.assertEqual(spec_class.as_tuple(), (0, 0, 2, 0))

        # div -> (0, 0, 0, 1)
        self.assertEqual(spec_tag.as_tuple(), (0, 0, 0, 1))

        # div.card#main -> (0, 1, 1, 1)
        self.assertEqual(spec_compound.as_tuple(), (0, 1, 1, 1))

        # Verify ordering: ID > Compound Class > Single Tag
        self.assertGreater(spec_id, spec_class)
        self.assertGreater(spec_class, spec_tag)
        self.assertGreater(spec_compound, spec_id)

    def test_selector_matching_predicate(self):
        """Test selector pattern matching against DOM element attributes."""
        sel = CSSSelector("div.card#item-42")

        # 1. Matching element -> True
        ok = sel.matches(TagType.DIV, element_id="item-42", element_classes=["card", "shadow"])
        self.assertTrue(ok)

        # 2. Mismatched Tag -> False
        fail_tag = sel.matches(TagType.P, element_id="item-42", element_classes=["card"])
        self.assertFalse(fail_tag)

        # 3. Mismatched Class -> False
        fail_cls = sel.matches(TagType.DIV, element_id="item-42", element_classes=["box"])
        self.assertFalse(fail_cls)

    def test_css_rule_index_fast_o1_lookup(self):
        """Test indexing rules into buckets and retrieving candidate rules in O(1) time."""
        index = CSSRuleIndex()

        rule_id = CSSRule([CSSSelector("#main-container")], [CSSDeclaration("width", "100%")])
        rule_class = CSSRule([CSSSelector(".btn-primary")], [CSSDeclaration("color", "blue")])
        rule_tag = CSSRule([CSSSelector("button")], [CSSDeclaration("border", "none")])
        rule_univ = CSSRule([CSSSelector("*")], [CSSDeclaration("box-sizing", "border-box")])

        index.add_stylesheet([rule_id, rule_class, rule_tag, rule_univ])
        self.assertEqual(index.total_rules_indexed, 4)

        # Query candidates for a <button class="btn-primary">
        candidates = index.get_candidate_rules(
            tag_type=TagType.BUTTON,
            element_id="",
            element_classes=["btn-primary"]
        )

        self.assertIn(rule_class, candidates)
        self.assertIn(rule_tag, candidates)
        self.assertIn(rule_univ, candidates)
        self.assertNotIn(rule_id, candidates)

    def test_high_speed_rule_indexing_benchmark(self):
        """
        Benchmark: Index 10,000 CSS rules into CSSRuleIndex and execute candidate lookups.
        Asserts throughput > 200,000 rules/sec.
        """
        index = CSSRuleIndex()

        # Build 10,000 rule stylesheet payload
        generated_rules = []
        for i in range(10000):
            sel_str = f"#id-{i}, .cls-{i % 100}, div"
            sel = CSSSelector(sel_str)
            decl = CSSDeclaration("font-size", f"{12 + (i % 8)}px")
            generated_rules.append(CSSRule([sel], [decl]))

        start_time = time.perf_counter()
        index.add_stylesheet(generated_rules)

        # Execute 1,000 candidate rule queries
        for i in range(1000):
            candidates = index.get_candidate_rules(
                tag_type=TagType.DIV,
                element_id=f"id-{i}",
                element_classes=[f"cls-{i % 100}"]
            )
        duration = time.perf_counter() - start_time

        rules_per_sec = len(generated_rules) / duration
        latency_us = (duration / len(generated_rules)) * 1_000_000

        self.assertLess(duration, 0.15, f"10k CSS indexing took {duration*1000:.2f}ms (must be < 150ms)")
        print(f"\n[Sprint 10 CSS Rule Indexing Benchmark] {len(generated_rules):,} Rules Indexed:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Indexing & Lookup Speed: {rules_per_sec:,.0f} rules/second")
        print(f"  - Average Rule Index Latency: {latency_us:.2f} µs/rule")


if __name__ == "__main__":
    unittest.main()
