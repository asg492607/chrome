import tkinter as tk

class StatusIndicator(tk.Frame):
    def __init__(self, parent, label_text, initial_status="Offline", *args, **kwargs):
        super().__init__(parent, bg="#1e293b", *args, **kwargs)
        
        self.lbl_title = tk.Label(self, text=label_text, font=("Arial", 10, "bold"), bg="#1e293b", fg="#cbd5e1")
        self.lbl_title.pack(side="left", padx=5)
        
        self.canvas = tk.Canvas(self, width=16, height=16, bg="#1e293b", highlightthickness=0)
        self.canvas.pack(side="left", padx=5)
        self.circle = self.canvas.create_oval(2, 2, 14, 14, fill="#ef4444", outline="")
        
        self.lbl_status = tk.Label(self, text=initial_status, font=("Courier", 10), bg="#1e293b", fg="#94a3b8")
        self.lbl_status.pack(side="left", padx=5)
        
        self.set_status(initial_status)

    def set_status(self, status):
        self.lbl_status.config(text=status)
        if status.lower() == "online" or status.lower() == "active":
            self.canvas.itemconfig(self.circle, fill="#10b981")
            self.lbl_status.config(fg="#34d399")
        elif status.lower() == "offline":
            self.canvas.itemconfig(self.circle, fill="#ef4444")
            self.lbl_status.config(fg="#f87171")
        else:
            self.canvas.itemconfig(self.circle, fill="#f59e0b")
            self.lbl_status.config(fg="#fbbf24")
