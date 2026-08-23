import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from browser_engine.browser_models import LayoutBox
from browser_engine.layout.box_model import BoxModel
from browser_engine.layout.text_layout import TextLayout

class LayoutEngine:
    def __init__(self, canvas_width=760, padding_x=20, padding_y=20):
        self.canvas_width = canvas_width
        self.padding_x = padding_x
        self.padding_y = padding_y
        self.boxes = []
        self.cursor_x = padding_x
        self.cursor_y = padding_y
        self.line_height = 22
        self.text_layout = TextLayout()

    def compute_layout(self, dom_root):
        self.boxes = []
        self.cursor_x = self.padding_x
        self.cursor_y = self.padding_y
        
        body_node = self._find_body(dom_root)
        if body_node:
            self._layout_node(body_node)
        else:
            self._layout_node(dom_root)
            
        return self.boxes

    def _find_body(self, node):
        if node.tag_name == "body":
            return node
        for child in node.children:
            found = self._find_body(child)
            if found:
                return found
        return None

    def _layout_node(self, node):
        if node.tag_name == "br":
            self.cursor_x = self.padding_x
            self.cursor_y += self.line_height
            return

        style = node.computed_style
        display = style.get("display", "block")
        bg_color = style.get("background-color")
        
        if display == "block":
            if self.cursor_x > self.padding_x:
                self.cursor_x = self.padding_x
                self.cursor_y += self.line_height
                
            avail_width = self.canvas_width - 2 * self.padding_x
            m_top, m_bottom, m_left, m_right, block_w_px = BoxModel.compute_margins(style, avail_width)
            p_top, p_bottom, p_left, p_right = BoxModel.compute_padding(style)

            block_start_y = self.cursor_y + m_top
            self.cursor_y = block_start_y + p_top
            
            old_padding_x = self.padding_x
            self.padding_x = old_padding_x + m_left + p_left
            self.cursor_x = self.padding_x
            
            if bg_color and bg_color != "transparent":
                bg_box = LayoutBox(
                    node=node,
                    box_type="block_bg",
                    x=old_padding_x + m_left,
                    y=block_start_y,
                    w=block_w_px,
                    h=0,
                    style=style
                )
                self.boxes.append(bg_box)
            else:
                bg_box = None
                
            if node.tag_name == "hr":
                self.boxes.append(LayoutBox(
                    node=node,
                    box_type="hr",
                    x=old_padding_x + m_left + p_left,
                    y=block_start_y + p_top + 5,
                    w=block_w_px - p_left - p_right,
                    h=2,
                    style=style
                ))
                self.cursor_y += 15
            else:
                for child in node.children:
                    self._layout_node(child)
                    
            block_height = self.cursor_y - block_start_y
            if block_height == p_top and node.tag_name in ["h1", "h2", "h3", "p", "div"]:
                block_height += self.line_height
                
            if bg_box:
                bg_box.h = block_height + p_bottom
                
            self.padding_x = old_padding_x
            self.cursor_x = self.padding_x
            self.cursor_y = block_start_y + block_height + p_bottom + m_bottom
                
        else:
            if node.tag_name == "text":
                self._layout_text_node(node)
            else:
                for child in node.children:
                    self._layout_node(child)

    def _layout_text_node(self, node):
        text = node.text
        style = node.parent.computed_style if node.parent else {}
        font = self.text_layout.get_font(style)
        
        size_px = abs(font.actual("size"))
        self.line_height = max(22, int(size_px * 1.5))
        
        is_link = False
        temp = node.parent
        link_url = ""
        while temp is not None:
            if temp.tag_name == "a":
                is_link = True
                link_url = temp.attrs.get("href", "")
                break
            temp = temp.parent

        text = self.text_layout.sanitize_text(text)
        if not text:
            return

        words = text.split(" ")
        for word in words:
            if not word:
                continue
                
            word_w = self.text_layout.measure_word(font, word)
            space_w = self.text_layout.measure_space(font)
            
            right_boundary = self.canvas_width - self.padding_x
            if self.cursor_x + word_w > right_boundary:
                self.cursor_x = self.padding_x
                self.cursor_y += self.line_height

            self.boxes.append(LayoutBox(
                node=node,
                box_type="link_word" if is_link else "text_word",
                x=self.cursor_x,
                y=self.cursor_y,
                w=word_w,
                h=self.line_height,
                text=word,
                style={**style, "link_url": link_url}
            ))
            self.cursor_x += word_w + space_w
