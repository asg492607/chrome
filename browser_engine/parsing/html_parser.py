from browser_engine.browser_models import Node

class HTMLParser:
    def __init__(self):
        pass

    def parse(self, html_text):
        """
        Parses HTML string into tokens and builds the DOM tree.
        (Refactored: Ideally this would just tokenize, and DOM builder would build it,
        but we keep them together under parsing for simplicity in this phase).
        """
        root = Node("root")
        current_node = root
        
        i = 0
        n = len(html_text)
        
        while i < n:
            if html_text[i] == "<":
                if html_text[i:i+4] == "<!--":
                    i += 4
                    while i < n and html_text[i:i+3] != "-->":
                        i += 1
                    i += 3
                    continue
                
                i += 1
                tag_start = i
                in_quote = False
                quote_char = None
                
                while i < n:
                    c = html_text[i]
                    if c in ['"', "'"]:
                        if not in_quote:
                            in_quote = True
                            quote_char = c
                        elif quote_char == c:
                            in_quote = False
                            quote_char = None
                    elif c == ">" and not in_quote:
                        break
                    i += 1
                
                tag_content = html_text[tag_start:i].strip()
                i += 1
                
                if not tag_content:
                    continue
                
                if tag_content.startswith("/"):
                    tag_name = tag_content[1:].strip().lower()
                    temp = current_node
                    while temp.parent is not None:
                        if temp.tag_name == tag_name:
                            current_node = temp.parent
                            break
                        temp = temp.parent
                else:
                    is_self_closing = False
                    if tag_content.endswith("/"):
                        is_self_closing = True
                        tag_content = tag_content[:-1].strip()
                    
                    tag_name, attrs = self._parse_tag_content(tag_content)
                    
                    if tag_name in ["img", "br", "hr", "meta", "link", "input"]:
                        is_self_closing = True
                    
                    new_node = Node(tag_name, attrs=attrs)
                    current_node.add_child(new_node)
                    
                    if tag_name in ["style", "script"]:
                        closing_tag = f"</{tag_name}>"
                        content_start = i
                        while i < n and html_text[i:i+len(closing_tag)].lower() != closing_tag:
                            i += 1
                        raw_text = html_text[content_start:i]
                        if raw_text:
                            new_node.add_child(Node("text", text=raw_text))
                        i += len(closing_tag) 
                    elif not is_self_closing:
                        current_node = new_node
            else:
                text_start = i
                while i < n and html_text[i] != "<":
                    i += 1
                text_content = html_text[text_start:i]
                if text_content.strip() or ("\n" not in text_content and text_content):
                    current_node.add_child(Node("text", text=text_content))
                    
        return root

    def _parse_tag_content(self, tag_content):
        parts = tag_content.split(None, 1)
        tag_name = parts[0].lower()
        if len(parts) == 1:
            return tag_name, {}
            
        attr_str = parts[1]
        attrs = {}
        
        idx = 0
        length = len(attr_str)
        while idx < length:
            while idx < length and attr_str[idx].isspace():
                idx += 1
            if idx >= length:
                break
            
            key_start = idx
            while idx < length and not attr_str[idx].isspace() and attr_str[idx] != "=":
                idx += 1
            key = attr_str[key_start:idx].lower()
            
            while idx < length and attr_str[idx].isspace():
                idx += 1
            
            if idx < length and attr_str[idx] == "=":
                idx += 1 
                while idx < length and attr_str[idx].isspace():
                    idx += 1
                if idx >= length:
                    attrs[key] = ""
                    break
                
                c = attr_str[idx]
                if c in ['"', "'"]:
                    quote_char = c
                    idx += 1
                    val_start = idx
                    while idx < length and attr_str[idx] != quote_char:
                        idx += 1
                    val = attr_str[val_start:idx]
                    idx += 1 
                else:
                    val_start = idx
                    while idx < length and not attr_str[idx].isspace():
                        idx += 1
                    val = attr_str[val_start:idx]
                attrs[key] = val
            else:
                if key:
                    attrs[key] = "true"
                    
        return tag_name, attrs
