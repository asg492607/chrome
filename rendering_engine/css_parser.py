"""
CSS3 Selector Parser, W3C Specificity Calculator & O(1) Rule Indexing Engine.
Provides CSS tokenization, 4-tuple specificity scoring (inline, ids, classes, tags),
and multi-bucket rule indexing for instant style cascade matching.
"""

import sys
import os
import re
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Set, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core_platform.tag_constants import TagType, TAG_NAME_TO_TYPE


class CSSSpecificity:
    """
    W3C Standard CSS Specificity 4-Tuple: (inline, ids, classes, tags).
    Implements full comparison operators for cascade sorting.
    """
    def __init__(self, inline: int = 0, ids: int = 0, classes: int = 0, tags: int = 0):
        self.inline = inline
        self.ids = ids
        self.classes = classes
        self.tags = tags

    def as_tuple(self) -> Tuple[int, int, int, int]:
        return (self.inline, self.ids, self.classes, self.tags)

    def __lt__(self, other: "CSSSpecificity") -> bool:
        return self.as_tuple() < other.as_tuple()

    def __le__(self, other: "CSSSpecificity") -> bool:
        return self.as_tuple() <= other.as_tuple()

    def __gt__(self, other: "CSSSpecificity") -> bool:
        return self.as_tuple() > other.as_tuple()

    def __ge__(self, other: "CSSSpecificity") -> bool:
        return self.as_tuple() >= other.as_tuple()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CSSSpecificity):
            return False
        return self.as_tuple() == other.as_tuple()

    def __repr__(self) -> str:
        return f"({self.inline},{self.ids},{self.classes},{self.tags})"


class CSSSelector:
    """Represents a single CSS Selector with specificity calculation."""
    def __init__(self, raw_selector: str):
        self.raw_text = raw_selector.strip()
        self.tag_name: Optional[str] = None
        self.id_name: Optional[str] = None
        self.class_names: List[str] = []
        self.tag_type: Optional[TagType] = None
        self.specificity = CSSSpecificity()

        self._parse_selector()

    def _parse_selector(self) -> None:
        text = self.raw_text
        if not text:
            return

        # Check for ID selector (#id)
        id_match = re.search(r'#([a-zA-Z0-9_-]+)', text)
        if id_match:
            self.id_name = id_match.group(1).lower()

        # Check for class selectors (.class)
        classes = re.findall(r'\.([a-zA-Z0-9_-]+)', text)
        if classes:
            self.class_names = [c.lower() for c in classes]

        # Check for tag selector (element name)
        clean = re.sub(r'#[a-zA-Z0-9_-]+|\.[a-zA-Z0-9_-]+|:[a-zA-Z0-9_-]+', '', text).strip()
        if clean and clean != '*':
            self.tag_name = clean.lower()
            self.tag_type = TAG_NAME_TO_TYPE.get(self.tag_name, TagType.CUSTOM)

        # Calculate W3C Specificity
        id_count = 1 if self.id_name else 0
        class_count = len(self.class_names)
        tag_count = 1 if self.tag_name else 0

        self.specificity = CSSSpecificity(
            inline=0,
            ids=id_count,
            classes=class_count,
            tags=tag_count
        )

    def matches(self, tag_type: TagType, element_id: str = "", element_classes: Any = None) -> bool:
        """Evaluates whether this selector matches a given target element."""
        if element_classes is None:
            elem_set = set()
        elif isinstance(element_classes, set):
            elem_set = element_classes
        else:
            elem_set = {c.strip().lower() for c in element_classes if c.strip()}

        # Check ID match
        if self.id_name:
            if element_id != self.id_name:
                return False

        # Check Tag Type match
        if self.tag_type is not None:
            if tag_type != self.tag_type:
                return False

        # Check Class matches
        if self.class_names:
            for cls in self.class_names:
                if cls not in elem_set:
                    return False

        return True



class CSSDeclaration:
    """Represents a single CSS property declaration (e.g. `color: red !important;`)."""
    def __init__(self, property_name: str, value: str):
        self.property_name = property_name.strip().lower()
        val = value.strip()
        self.is_important = val.lower().endswith("!important")
        if self.is_important:
            val = val[:-10].strip()
        self.value = val

    def __repr__(self) -> str:
        imp = " !important" if self.is_important else ""
        return f"{self.property_name}: {self.value}{imp}"


class CSSRule:
    """Represents a single CSS Rule containing selectors, declarations, and specificity score."""
    def __init__(self, selectors: List[CSSSelector], declarations: List[CSSDeclaration]):
        self.selectors = selectors
        self.declarations = declarations
        self.max_specificity = max((s.specificity for s in selectors), default=CSSSpecificity())

    def __repr__(self) -> str:
        sel_str = ", ".join(s.raw_text for s in self.selectors)
        return f"CSSRule({sel_str} {{ {len(self.declarations)} decls }})"


class CSSParser:
    """Parses raw CSS stylesheet source text into a structured list of CSSRule objects."""

    @staticmethod
    def parse_stylesheet(css_text: str) -> List[CSSRule]:
        rules: List[CSSRule] = []

        # Strip comments /* ... */
        clean_css = re.sub(r'/\*.*?\*/', '', css_text, flags=re.DOTALL)

        # Match rule blocks: selector_part { declaration_part }
        rule_blocks = re.findall(r'([^{]+)\{([^}]+)\}', clean_css)

        for sel_part, decl_part in rule_blocks:
            sel_part = sel_part.strip()
            if not sel_part:
                continue

            # Parse selectors separated by comma
            raw_selectors = sel_part.split(',')
            selectors = [CSSSelector(s) for s in raw_selectors if s.strip()]

            # Parse declarations separated by semicolon
            declarations: List[CSSDeclaration] = []
            raw_decls = decl_part.split(';')
            for raw_d in raw_decls:
                if ':' in raw_d:
                    prop, val = raw_d.split(':', 1)
                    declarations.append(CSSDeclaration(prop, val))

            if selectors and declarations:
                rules.append(CSSRule(selectors, declarations))

        return rules


class CSSRuleIndex:
    """
    High-Speed O(1) Bucketed Rule Indexing Engine.
    Indexes rules by ID, Class, and TagType for instant candidate rule retrieval.
    """

    def __init__(self):
        # Index Buckets
        self.id_index: Dict[str, List[CSSRule]] = {}
        self.class_index: Dict[str, List[CSSRule]] = {}
        self.tag_index: Dict[TagType, List[CSSRule]] = {}
        self.universal_index: List[CSSRule] = []

        self.total_rules_indexed = 0

    def add_stylesheet(self, rules: List[CSSRule]) -> None:
        """Indexes a list of CSSRules into target lookup buckets."""
        for rule in rules:
            self.add_rule(rule)

    def add_rule(self, rule: CSSRule) -> None:
        """Indexes a single CSSRule based on its selectors."""
        self.total_rules_indexed += 1
        is_indexed = False

        for selector in rule.selectors:
            if selector.id_name:
                if selector.id_name not in self.id_index:
                    self.id_index[selector.id_name] = []
                self.id_index[selector.id_name].append(rule)
                is_indexed = True

            elif selector.class_names:
                for cls in selector.class_names:
                    if cls not in self.class_index:
                        self.class_index[cls] = []
                    self.class_index[cls].append(rule)
                is_indexed = True

            elif selector.tag_type is not None:
                if selector.tag_type not in self.tag_index:
                    self.tag_index[selector.tag_type] = []
                self.tag_index[selector.tag_type].append(rule)
                is_indexed = True

        if not is_indexed:
            self.universal_index.append(rule)

    def get_candidate_rules(
        self,
        tag_type: TagType,
        element_id: str = "",
        element_classes: Optional[List[str]] = None
    ) -> List[CSSRule]:
        """
        Retrieves candidate rules matching target element in O(1) bucket lookups.
        Returns deduplicated rules sorted by specificity.
        """
        if element_classes is None:
            element_classes = []

        candidates_set: Set[CSSRule] = set()

        # 1. Check ID Bucket (O(1))
        clean_id = element_id.strip().lower()
        if clean_id and clean_id in self.id_index:
            candidates_set.update(self.id_index[clean_id])

        # 2. Check Class Buckets (O(1))
        for cls in element_classes:
            clean_cls = cls.strip().lower()
            if clean_cls in self.class_index:
                candidates_set.update(self.class_index[clean_cls])

        # 3. Check TagType Bucket (O(1))
        if tag_type in self.tag_index:
            candidates_set.update(self.tag_index[tag_type])

        # 4. Include Universal Rules
        candidates_set.update(self.universal_index)

        # Sort candidate rules by specificity
        candidate_list = list(candidates_set)
        candidate_list.sort(key=lambda r: r.max_specificity)
        return candidate_list


# Standard W3C Inherited CSS Properties
INHERITED_PROPERTIES: Set[str] = {
    "color",
    "font-family",
    "font-size",
    "font-weight",
    "font-style",
    "line-height",
    "letter-spacing",
    "text-align",
    "text-indent",
    "visibility",
    "white-space",
    "word-spacing"
}

# User Agent Default Stylesheet (Base Browser Defaults)
DEFAULT_UA_STYLESHEET: str = """
html, body { display: block; margin: 0; padding: 0; color: #000000; font-family: sans-serif; font-size: 16px; line-height: 1.2; visibility: visible; }
div, section, article, nav, header, footer, main, p, h1, h2, h3, h4, h5, h6, ul, ol, li { display: block; }
span, a, b, i, strong, em, code { display: inline; }
h1 { font-size: 32px; font-weight: bold; margin: 16px 0; }
h2 { font-size: 24px; font-weight: bold; margin: 12px 0; }
h3 { font-size: 18px; font-weight: bold; margin: 8px 0; }
a { color: #0066cc; text-decoration: underline; }
"""


class CSSCascadeEngine:
    """
    W3C CSS Cascade Resolution & Inherited Property Propagation Engine.
    Computes final styles for DOM entities and populates bank.computed_styles_pool in top-down O(N) pass.
    """

    def __init__(self, rule_index: Optional[CSSRuleIndex] = None):
        self.rule_index = rule_index if rule_index is not None else CSSRuleIndex()
        self.ua_rule_index = CSSRuleIndex()
        
        # Load default User Agent stylesheet
        ua_rules = CSSParser.parse_stylesheet(DEFAULT_UA_STYLESHEET)
        self.ua_rule_index.add_stylesheet(ua_rules)

        self.total_nodes_styled = 0
        self.total_properties_computed = 0

    def resolve_element_style(
        self,
        bank: Any,
        node_id: int,
        parent_id: int = 0xFFFFFFFF
    ) -> Dict[str, str]:
        """
        Computes final cascading style dictionary for a single DOM entity.
        Resolves UA < Author < !important precedence and propagates inherited parent styles.
        """
        if node_id >= bank.count:
            return {}

        entity = bank.entities[node_id]
        tag_type = TagType(entity.tag_type)

        attrs = bank.attr_pool.get(node_id, {})
        raw_id = attrs.get("id", "")
        clean_id = raw_id.strip().lower()
        raw_class = attrs.get("class", "")
        element_classes = [c.strip() for c in raw_class.split() if c.strip()]
        element_classes_set = {c.lower() for c in element_classes}

        # 1. Gather candidate rules from UA and Author indices
        ua_candidates = self.ua_rule_index.get_candidate_rules(tag_type, clean_id, element_classes)
        author_candidates = self.rule_index.get_candidate_rules(tag_type, clean_id, element_classes)

        # Collect tuples: (is_important, specificity, declaration)
        collected_decls: List[Tuple[bool, CSSSpecificity, CSSDeclaration]] = []

        # Process UA rules (base level)
        for rule in ua_candidates:
            for selector in rule.selectors:
                if selector.matches(tag_type, clean_id, element_classes_set):
                    for decl in rule.declarations:
                        collected_decls.append((decl.is_important, CSSSpecificity(0, 0, 0, 0), decl))
                    break

        # Process Author rules (higher priority)
        for rule in author_candidates:
            for selector in rule.selectors:
                if selector.matches(tag_type, clean_id, element_classes_set):
                    for decl in rule.declarations:
                        collected_decls.append((decl.is_important, selector.specificity, decl))
                    break

        # Process inline style attribute (Highest Priority: Specificity (1, 0, 0, 0))
        inline_style = attrs.get("style", "").strip()
        if inline_style:
            for raw_d in inline_style.split(";"):
                if ":" in raw_d:
                    prop, val = raw_d.split(":", 1)
                    decl = CSSDeclaration(prop, val)
                    collected_decls.append((decl.is_important, CSSSpecificity(1, 0, 0, 0), decl))

        # Sort declarations: normal rules by specificity first, !important rules on top

        collected_decls.sort(key=lambda t: (1 if t[0] else 0, t[1]))

        # Apply declarations in order (later/higher specificity overwrites lower)
        computed: Dict[str, str] = {}
        for _, _, decl in collected_decls:
            computed[decl.property_name] = decl.value

        # 2. Inherited Property Propagation from Parent
        if parent_id != 0xFFFFFFFF and parent_id in bank.computed_styles_pool:
            parent_computed = bank.computed_styles_pool[parent_id]
            for inh_prop in INHERITED_PROPERTIES:
                if inh_prop not in computed and inh_prop in parent_computed:
                    computed[inh_prop] = parent_computed[inh_prop]

        # Store into memory bank
        bank.computed_styles_pool[node_id] = computed
        self.total_nodes_styled += 1
        self.total_properties_computed += len(computed)
        return computed

    def resolve_tree_styles(self, bank: Any, root_id: int) -> int:
        """
        Top-down traversal of DocumentTreeMemoryBank.
        Guarantees parent styles are computed before children for 100% accurate inheritance.
        """
        if root_id >= bank.count:
            return 0

        queue: List[Tuple[int, int]] = [(root_id, 0xFFFFFFFF)] # (node_id, parent_id)
        nodes_styled = 0

        while queue:
            curr_id, p_id = queue.pop(0)
            self.resolve_element_style(bank, curr_id, p_id)
            nodes_styled += 1

            # Queue children
            curr_ent = bank.entities[curr_id]
            child_id = curr_ent.first_child_index
            while child_id != 0xFFFFFFFF and child_id < bank.count:
                queue.append((child_id, curr_id))
                child_id = bank.entities[child_id].next_sibling_index

        return nodes_styled

