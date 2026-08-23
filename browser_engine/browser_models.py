class Node:
    def __init__(self, tag_name, attrs=None, text="", parent=None):
        self.tag_name = tag_name.lower()
        self.attrs = attrs if attrs else {}
        self.text = text  # Contains text if tag_name is 'text'
        self.parent = parent
        self.children = []
        self.computed_style = {} # Assigned during CSS parsing
        
    def add_child(self, child_node):
        child_node.parent = self
        self.children.append(child_node)

    def __repr__(self):
        if self.tag_name == "text":
            return f"TextNode({repr(self.text)})"
        return f"ElementNode(<{self.tag_name}>, attrs={self.attrs}, children={len(self.children)})"

    def print_tree(self, indent=0):
        spacing = "  " * indent
        if self.tag_name == "text":
            print(f"{spacing}text: {repr(self.text)}")
        else:
            print(f"{spacing}<{self.tag_name} attrs={self.attrs}>")
            for child in self.children:
                child.print_tree(indent + 1)
            print(f"{spacing}</{self.tag_name}>")


class LayoutBox:
    def __init__(self, node, box_type, x, y, w, h, text="", style=None):
        self.node = node
        self.box_type = box_type  # 'block_bg', 'text_word', 'link_word', 'hr'
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.text = text
        self.style = style if style else {}

    def __repr__(self):
        return f"LayoutBox({self.box_type}, x={self.x}, y={self.y}, w={self.w}, h={self.h}, text={repr(self.text)})"
