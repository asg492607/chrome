import tkinter as tk

class MetricCard(tk.Frame):
    def __init__(self, parent, title, value="0", unit="", *args, **kwargs):
        super().__init__(parent, bg="#334155", padx=10, pady=10, *args, **kwargs)
        
        self.lbl_title = tk.Label(self, text=title, font=("Arial", 9), bg="#334155", fg="#94a3b8")
        self.lbl_title.pack(anchor="w")
        
        self.value_frame = tk.Frame(self, bg="#334155")
        self.value_frame.pack(anchor="w", pady=(5, 0))
        
        self.lbl_value = tk.Label(self.value_frame, text=value, font=("Arial", 16, "bold"), bg="#334155", fg="#f8fafc")
        self.lbl_value.pack(side="left")
        
        self.lbl_unit = tk.Label(self.value_frame, text=unit, font=("Arial", 10), bg="#334155", fg="#cbd5e1")
        self.lbl_unit.pack(side="left", padx=(4, 0), fill="y")

    def set_value(self, value):
        self.lbl_value.config(text=str(value))
