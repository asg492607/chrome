import re

class CSSParser:
    def expand_shorthand(self, prop, val):
        expanded = {}
        val_parts = val.split()
        if not val_parts:
            return expanded
            
        if prop in ["margin", "padding"]:
            if len(val_parts) == 1:
                t = b = l = r = val_parts[0]
            elif len(val_parts) == 2:
                t = b = val_parts[0]
                l = r = val_parts[1]
            elif len(val_parts) == 3:
                t = val_parts[0]
                l = r = val_parts[1]
                b = val_parts[2]
            else:
                t = val_parts[0]
                r = val_parts[1]
                b = val_parts[2]
                l = val_parts[3]
                
            expanded[f"{prop}-top"] = t
            expanded[f"{prop}-bottom"] = b
            expanded[f"{prop}-left"] = l
            expanded[f"{prop}-right"] = r
        elif prop == "background":
            expanded["background-color"] = val
        else:
            expanded[prop] = val
        return expanded

    def parse_stylesheet(self, css_text):
        stylesheet_rules = {}
        blocks = re.findall(r'([^{]+)\s*\{\s*([^}]+)\s*\}', css_text)
        for selector, rules_body in blocks:
            selector = selector.strip().lower()
            if selector not in stylesheet_rules:
                stylesheet_rules[selector] = {}
                
            declarations = rules_body.split(";")
            for decl in declarations:
                if ":" in decl:
                    prop, val = decl.split(":", 1)
                    prop = prop.strip().lower()
                    val = val.strip().lower()
                    for ep, ev in self.expand_shorthand(prop, val).items():
                        stylesheet_rules[selector][ep] = ev
        return stylesheet_rules

    def parse_inline_style(self, style_str):
        styles = {}
        if not style_str:
            return styles
        declarations = style_str.split(";")
        for decl in declarations:
            if ":" in decl:
                prop, val = decl.split(":", 1)
                prop = prop.strip().lower()
                val = val.strip().lower()
                for ep, ev in self.expand_shorthand(prop, val).items():
                    styles[ep] = ev
        return styles
