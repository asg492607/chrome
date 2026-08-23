import tkinter as tk
from tkinter import ttk

class BrowserWindow(tk.Tk):
    def __init__(self, browser_controller):
        super().__init__()
        self.controller = browser_controller
        self.title("PacketForge - Browser Engine")
        self.geometry("1100x700")
        self.configure(bg="#0f172a")
        
        self.link_map = {}
        
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("TLabel", background="#1e293b", foreground="#cbd5e1")
        self.style.configure("TButton", background="#334155", foreground="#ffffff", borderwidth=0)
        self.style.map("TButton", background=[("active", "#475569")])

        self._build_ui()
        
    def _build_ui(self):
        nav_frame = tk.Frame(self, bg="#1e293b", height=50, bd=0)
        nav_frame.pack(side="top", fill="x")

        self.btn_back = tk.Button(nav_frame, text=" ⏴ ", font=("Arial", 12), bg="#334155", fg="#ffffff", activebackground="#475569", activeforeground="#ffffff", bd=0, relief="flat", command=self.controller.go_back)
        self.btn_back.pack(side="left", padx=5, pady=5)

        self.btn_forward = tk.Button(nav_frame, text=" ⏵ ", font=("Arial", 12), bg="#334155", fg="#ffffff", activebackground="#475569", activeforeground="#ffffff", bd=0, relief="flat", command=self.controller.go_forward)
        self.btn_forward.pack(side="left", padx=5, pady=5)

        self.btn_refresh = tk.Button(nav_frame, text=" ⟳ ", font=("Arial", 12), bg="#334155", fg="#ffffff", activebackground="#475569", activeforeground="#ffffff", bd=0, relief="flat", command=self.controller.refresh)
        self.btn_refresh.pack(side="left", padx=5, pady=5)

        self.btn_home = tk.Button(nav_frame, text=" 🏠 ", font=("Arial", 12), bg="#334155", fg="#ffffff", activebackground="#475569", activeforeground="#ffffff", bd=0, relief="flat", command=self.controller.go_home)
        self.btn_home.pack(side="left", padx=5, pady=5)

        self.url_entry = tk.Entry(nav_frame, font=("Arial", 12), bg="#0f172a", fg="#cbd5e1", insertbackground="#cbd5e1", bd=0, highlightthickness=1, highlightbackground="#334155", highlightcolor="#818cf8")
        self.url_entry.pack(side="left", fill="x", expand=True, padx=10, pady=8)
        self.url_entry.bind("<Return>", lambda e: self.controller.navigate_from_bar())
        self.url_entry.insert(0, "asgsearch.local")

        btn_go = tk.Button(nav_frame, text=" GO ", font=("Arial", 10, "bold"), bg="#818cf8", fg="#ffffff", activebackground="#6366f1", activeforeground="#ffffff", bd=0, relief="flat", command=self.controller.navigate_from_bar)
        btn_go.pack(side="left", padx=5, pady=5)

        split_pane = tk.PanedWindow(self, orient="horizontal", bd=0, bg="#0f172a")
        split_pane.pack(fill="both", expand=True)

        web_frame = tk.Frame(split_pane, bg="#0f172a")
        split_pane.add(web_frame, width=760)

        self.canvas = tk.Canvas(web_frame, bg="#0f172a", highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(web_frame, command=self.canvas.yview)
        scrollbar.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        diag_frame = tk.Frame(split_pane, bg="#1e293b", padx=10, pady=10)
        split_pane.add(diag_frame, width=340)

        diag_title = tk.Label(diag_frame, text="NETWORK TELEMETRY", font=("Courier", 14, "bold"), bg="#1e293b", fg="#34d399")
        diag_title.pack(anchor="w", pady=(0, 10))

        status_box = tk.LabelFrame(diag_frame, text="Interface Status", font=("Arial", 10, "bold"), bg="#1e293b", fg="#818cf8", padx=8, pady=8)
        status_box.pack(fill="x", pady=5)

        self.lbl_ip = tk.Label(status_box, text="IP Address: Unassigned", font=("Courier", 10), bg="#1e293b", fg="#94a3b8")
        self.lbl_ip.pack(anchor="w")

        self.lbl_gateway = tk.Label(status_box, text="Gateway IP: Unassigned", font=("Courier", 10), bg="#1e293b", fg="#94a3b8")
        self.lbl_gateway.pack(anchor="w")

        self.lbl_dns = tk.Label(status_box, text="DNS Server: Unassigned", font=("Courier", 10), bg="#1e293b", fg="#94a3b8")
        self.lbl_dns.pack(anchor="w")

        self.btn_dhcp = tk.Button(status_box, text="Request DHCP IP", font=("Arial", 9, "bold"), bg="#10b981", fg="#ffffff", activebackground="#059669", activeforeground="#ffffff", bd=0, relief="flat", command=self.controller.request_dhcp_toggle)
        self.btn_dhcp.pack(fill="x", pady=(8, 0))

        proxy_box = tk.LabelFrame(diag_frame, text="Nginx Router Gate", font=("Arial", 10, "bold"), bg="#1e293b", fg="#818cf8", padx=8, pady=8)
        proxy_box.pack(fill="x", pady=5)

        lbl_proxy_addr = tk.Label(proxy_box, text=f"Reverse Proxy: 127.0.0.1:8282", font=("Courier", 10), bg="#1e293b", fg="#94a3b8")
        lbl_proxy_addr.pack(anchor="w")

        lbl_proxy_rules = tk.Label(proxy_box, text="Host Routing Rules:\n  - asgsearch.local -> Upstream :8082\n  - myblog.com      -> Upstream :8081\n  - news.com        -> Upstream :8081", font=("Courier", 9), bg="#1e293b", fg="#64748b", justify="left")
        lbl_proxy_rules.pack(anchor="w", pady=(4, 0))

        console_title = tk.Label(diag_frame, text="Packet Logs (Wireshark Mock):", font=("Arial", 10, "bold"), bg="#1e293b", fg="#cbd5e1")
        console_title.pack(anchor="w", pady=(15, 2))

        self.log_text = tk.Text(diag_frame, font=("Courier", 9), bg="#0f172a", fg="#a7f3d0", bd=0, highlightthickness=1, highlightbackground="#334155", state="disabled", height=20)
        self.log_text.pack(fill="both", expand=True)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def log_diagnostic(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def bind_link_events(self, item_id, url_target):
        self.canvas.tag_bind(item_id, "<Button-1>", lambda e, u=url_target: self.controller.navigate(u))
        self.canvas.tag_bind(item_id, "<Enter>", lambda e, id=item_id: self._on_link_enter(id))
        self.canvas.tag_bind(item_id, "<Leave>", lambda e, id=item_id: self._on_link_leave(id))

    def _on_link_enter(self, item_id):
        self.canvas.config(cursor="hand2")
        self.canvas.itemconfig(item_id, fill="#93c5fd")

    def _on_link_leave(self, item_id):
        self.canvas.config(cursor="")
        self.canvas.itemconfig(item_id, fill="#60a5fa")
