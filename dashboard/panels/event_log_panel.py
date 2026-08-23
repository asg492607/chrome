import tkinter as tk

class EventLogPanel(tk.LabelFrame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, text="System Event Log", font=("Arial", 10, "bold"), bg="#1e293b", fg="#e2e8f0", padx=10, pady=10, *args, **kwargs)
        
        self.log_text = tk.Text(self, font=("Courier", 9), bg="#0f172a", fg="#a7f3d0", bd=0, highlightthickness=1, highlightbackground="#334155", state="disabled", height=15)
        self.log_text.pack(fill="both", expand=True)

    def log(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def clear(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
