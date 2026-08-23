import tkinter as tk

class LineChart(tk.Canvas):
    def __init__(self, parent, width=300, height=150, bg="#1e293b", fg="#38bdf8", *args, **kwargs):
        super().__init__(parent, width=width, height=height, bg=bg, highlightthickness=0, *args, **kwargs)
        self.fg = fg
        self.data = []
        self.max_points = 50

    def update_data(self, value):
        self.data.append(value)
        if len(self.data) > self.max_points:
            self.data.pop(0)
        self.redraw()

    def redraw(self):
        self.delete("all")
        if not self.data:
            return

        w = int(self["width"])
        h = int(self["height"])
        
        max_val = max(self.data) if max(self.data) > 0 else 1
        
        points = []
        step_x = w / (self.max_points - 1)
        
        for i, val in enumerate(self.data):
            x = i * step_x
            y = h - (val / max_val * h)
            points.extend([x, y])
            
        if len(points) >= 4:
            self.create_line(points, fill=self.fg, width=2)
