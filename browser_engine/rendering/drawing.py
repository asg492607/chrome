class DrawingHelper:
    @staticmethod
    def draw_rect(canvas, x, y, w, h, bg_color):
        if bg_color and bg_color != "transparent":
            canvas.create_rectangle(x, y, x + w, y + h, fill=bg_color, outline="")

    @staticmethod
    def draw_line(canvas, x1, y1, x2, y2, color, width=1):
        canvas.create_line(x1, y1, x2, y2, fill=color, width=width)

    @staticmethod
    def draw_text(canvas, x, y, text, color, font, tags=None):
        if tags:
            return canvas.create_text(x, y, text=text, anchor="nw", fill=color, font=font, tags=tags)
        else:
            return canvas.create_text(x, y, text=text, anchor="nw", fill=color, font=font)
