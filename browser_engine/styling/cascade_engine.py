import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from browser_engine.parsing.css_parser import CSSParser
from browser_engine.styling.style_engine import StyleEngine

class CascadeEngine:
    def __init__(self):
        self.css_parser = CSSParser()
        self.global_rules = {}

    def apply_styles(self, dom_root):
        self.global_rules = {}
        self._harvest_style_blocks(dom_root)
        self._cascade_styles(dom_root, parent_style=StyleEngine.get_default_parent_style())

    def _harvest_style_blocks(self, node):
        if node.tag_name == "style":
            for child in node.children:
                if child.tag_name == "text":
                    rules = self.css_parser.parse_stylesheet(child.text)
                    for sel, props in rules.items():
                        if sel not in self.global_rules:
                            self.global_rules[sel] = {}
                        self.global_rules[sel].update(props)
        
        for child in node.children:
            self._harvest_style_blocks(child)

    def _selector_matches(self, selector, node):
        selector = selector.strip()
        if " " in selector:
            parts = selector.split()
            last_part = parts[-1]
            if not self._single_selector_matches(last_part, node):
                return False
                
            ancestor = node.parent
            for prefix_part in reversed(parts[:-1]):
                matched_ancestor = False
                while ancestor is not None:
                    if self._single_selector_matches(prefix_part, ancestor):
                        matched_ancestor = True
                        ancestor = ancestor.parent
                        break
                    ancestor = ancestor.parent
                if not matched_ancestor:
                    return False
            return True
        else:
            return self._single_selector_matches(selector, node)

    def _single_selector_matches(self, selector, node):
        if selector.startswith("."):
            class_name = selector[1:]
            node_class = node.attrs.get("class", "")
            return class_name in node_class.split()
        elif selector.startswith("#"):
            id_name = selector[1:]
            node_id = node.attrs.get("id", "")
            return id_name == node_id
        else:
            return selector == node.tag_name

    def _cascade_styles(self, node, parent_style):
        inheritable_props = ["color", "font-size", "font-family", "text-align"]
        node_style = {}
        for prop in inheritable_props:
            node_style[prop] = parent_style.get(prop)

        # Apply Tag defaults
        node_style.update(StyleEngine.get_tag_style(node.tag_name))

        # Overlay global stylesheet rules
        for selector, rules in self.global_rules.items():
            if self._selector_matches(selector, node):
                node_style.update(rules)

        # Overlay inline style attribute
        inline_style_str = node.attrs.get("style", "")
        inline_styles = self.css_parser.parse_inline_style(inline_style_str)
        node_style.update(inline_styles)

        node.computed_style = node_style

        for child in node.children:
            self._cascade_styles(child, node_style)
