import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from browser_engine.layout.text_layout import TextLayout
from browser_engine.rendering.drawing import DrawingHelper

class CanvasRenderer:
    def __init__(self, browser_window):
        self.browser_window = browser_window
        self.text_layout = TextLayout()

    def paint(self, canvas, layout_boxes):
        canvas.delete("all")
        self.browser_window.link_map.clear()
        
        # 1. Paint Backgrounds
        for box in layout_boxes:
            if box.box_type == "block_bg":
                bg = box.style.get("background-color")
                DrawingHelper.draw_rect(canvas, box.x, box.y, box.w, box.h, bg)
            elif box.box_type == "hr":
                DrawingHelper.draw_line(canvas, box.x, box.y, box.x + box.w, box.y, color="#334155", width=1)
                
        # 2. Paint Foreground (Text/Links)
        for box in layout_boxes:
            if box.box_type == "text_word":
                font = self.text_layout.get_font(box.style)
                color = box.style.get("color", "#cbd5e1")
                DrawingHelper.draw_text(canvas, box.x, box.y, box.text, color, font)
                
            elif box.box_type == "link_word":
                font = self.text_layout.get_font(box.style)
                color = box.style.get("color", "#60a5fa")
                
                item_id = DrawingHelper.draw_text(canvas, box.x, box.y, box.text, color, font, tags=("link",))
                
                url_target = box.style.get("link_url", "")
                self.browser_window.link_map[item_id] = url_target
                
                # Setup bindings on the browser window
                self.browser_window.bind_link_events(item_id, url_target)
                
        canvas.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))
