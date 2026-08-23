class StyleEngine:
    @staticmethod
    def get_default_parent_style():
        return {
            "color": "#cbd5e1",
            "background-color": "transparent",
            "font-size": "14px",
            "font-weight": "normal",
            "text-align": "left",
            "font-family": "Arial",
            "display": "block"
        }

    @staticmethod
    def get_tag_style(tag_name):
        node_style = {
            "background-color": "transparent",
            "font-weight": "normal",
            "display": "block" if tag_name not in ["a", "span", "b", "i", "text", "br"] else "inline"
        }
        
        if tag_name == "h1":
            node_style["font-size"] = "24px"
            node_style["font-weight"] = "bold"
        elif tag_name == "h2":
            node_style["font-size"] = "20px"
            node_style["font-weight"] = "bold"
        elif tag_name == "h3":
            node_style["font-size"] = "16px"
            node_style["font-weight"] = "bold"
        elif tag_name == "a":
            node_style["color"] = "#60a5fa"
            node_style["font-weight"] = "normal"
        elif tag_name in ["b", "strong"]:
            node_style["font-weight"] = "bold"
            node_style["display"] = "inline"
        elif tag_name in ["i", "em"]:
            node_style["font-style"] = "italic"
            node_style["display"] = "inline"
            
        return node_style
