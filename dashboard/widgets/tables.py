import tkinter as tk
from tkinter import ttk

class DataTable(ttk.Treeview):
    def __init__(self, parent, columns, *args, **kwargs):
        super().__init__(parent, columns=columns, show="headings", *args, **kwargs)
        for col in columns:
            self.heading(col, text=col.title())
            self.column(col, width=100, anchor="center")

    def insert_row(self, values):
        self.insert("", "end", values=values)
        
    def clear(self):
        for item in self.get_children():
            self.delete(item)
