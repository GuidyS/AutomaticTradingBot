import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import subprocess
import threading
import os
import json
import sys
import io
import time
from datetime import datetime

# --- Theme & Colors ---
BG_COLOR = "#0a0a0a"
PANEL_BG = "#141414"
INPUT_BG = "#2d2d2d"
ACCENT_YELLOW = "#ffb000"
ACCENT_GREEN = "#008000"
ACCENT_RED = "#cc0000"
TEXT_GRAY = "#888888"
TEXT_WHITE = "#ffffff"

# --- View Components ---

class DashboardView(ctk.CTkFrame):
    def __init__(self, master, app_main):
        super().__init__(master, fg_color="transparent")
        self.app_main = app_main
        
        # 1. Top Stats Row
        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.pack(side="top", fill="x", pady=(0, 15))
        
        self.create_stat_box(self.stats_frame, "BALANCE", "$0.00")
        self.create_stat_box(self.stats_frame, "EQUITY", "$0.00")
        self.create_stat_box(self.stats_frame, "FLOATING P&L", "+$0.00", color="#00cc00")
        self.create_stat_box(self.stats_frame, "DRAWDOWN", "0.00%", color=ACCENT_YELLOW)
        self.create_stat_box(self.stats_frame, "WIN RATE", "0.0%")
        self.create_stat_box(self.stats_frame, "OPEN POS", "0")

        # 2. Main Area
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True)
        
        left = ctk.CTkFrame(main, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=(0,10))
        
        # Bot Control
        ctrl = self.create_group(left, "> BOT_CONTROL", height=130)
        ctk.CTkLabel(ctrl, text="STRATEGY: DICKY-GRID-PRO-v1", font=ctk.CTkFont(size=10, weight="bold"), text_color=TEXT_GRAY).place(x=15, y=50)
        self.start_btn = ctk.CTkButton(ctrl, text="▶ START BOT", fg_color="transparent", border_color=ACCENT_YELLOW, border_width=1, 
                                       text_color=ACCENT_YELLOW, width=180, height=35)
        self.start_btn.place(x=400, y=40)
        self.em_btn = ctk.CTkButton(ctrl, text="⚠ EMERGENCY CLOSE", fg_color="#2a0000", border_color=ACCENT_RED, border_width=1, 
                                     text_color=ACCENT_RED, width=180, height=35)
        self.em_btn.place(x=400, y=85)

        # Log
        log_grp = self.create_group(left, "> REAL_TIME_ACTIVITY_LOG")
        self.log = ctk.CTkTextbox(log_grp, fg_color="#050505", font=ctk.CTkFont(family="Consolas", size=11))
        self.log.pack(fill="both", expand=True, padx=10, pady=10)

        # Right Panel
        right = ctk.CTkFrame(main, fg_color="transparent", width=300)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        
        self.create_group(right, "> AI_ENGINE", height=180)
        self.create_group(right, "> POSITIONS")
        self.create_group(right, "> RISK_MONITOR", height=80)

    def create_stat_box(self, parent, title, val, color="white"):
        f = ctk.CTkFrame(parent, fg_color=PANEL_BG, corner_radius=4)
        f.pack(side="left", fill="both", expand=True, padx=2)
        ctk.CTkLabel(f, text=title, font=ctk.CTkFont(size=9, weight="bold"), text_color=TEXT_GRAY).pack(pady=(12, 0))
        ctk.CTkLabel(f, text=val, font=ctk.CTkFont(size=22, weight="bold"), text_color=color).pack(pady=(0, 12))
        return f

    def create_group(self, parent, title, height=None):
        f = ctk.CTkFrame(parent, fg_color=PANEL_BG, corner_radius=4, height=height)
        f.pack(side="top", fill="both", expand=True if height is None else False, pady=(0, 10))
        if height: f.pack_propagate(False)
        ctk.CTkLabel(f, text=title, text_color=ACCENT_YELLOW, font=ctk.CTkFont(size=11, weight="bold"), anchor="w").pack(fill="x", padx=10, pady=5)
        return f

class SettingsView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        
        # 2 Column Layout
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True)

        left = ctk.CTkScrollableFrame(main, fg_color="transparent", label_text="# SYSTEM / CONFIGURATION", label_text_color="white")
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # Groups
        ai = self.create_group(left, "> AI_ENGINE & CONNECTIVITY")
        self.create_input(ai, "GEMINI_PRO_API_KEY", "", width=450)
        row_oll = ctk.CTkFrame(ai, fg_color="transparent")
        row_oll.pack(fill="x", padx=10, pady=5)
        self.create_input(row_oll, "OLLAMA_URL", "http://localhost:11434", pack_side="left")
        ctk.CTkComboBox(row_oll, values=["llama3.2", "llama3.1"], width=120).pack(side="left", padx=5, pady=(20,0))
        ctk.CTkButton(ai, text="TEST AI CONNECTIONS", fg_color="transparent", border_color=ACCENT_YELLOW, border_width=1, text_color=ACCENT_YELLOW).pack(pady=10)

        tg = self.create_group(left, "> TELEGRAM_NOTIFICATIONS")
        ctk.CTkCheckBox(tg, text="ENABLE_TELEGRAM_ALERTS [SPACE]", font=ctk.CTkFont(size=10)).pack(anchor="w", padx=10, pady=5)
        row_tg = ctk.CTkFrame(tg, fg_color="transparent")
        row_tg.pack(fill="x", padx=10, pady=5)
        self.create_input(row_tg, "BOT_TOKEN", "", width=200, pack_side="left")
        self.create_input(row_tg, "CHAT_ID", "", width=150, pack_side="left")

        risk = self.create_group(left, "> RISK & MONEY MANAGEMENT")
        row_r = ctk.CTkFrame(risk, fg_color="transparent")
        row_r.pack(fill="x", padx=10, pady=5)
        ctk.CTkComboBox(row_r, values=["PERCENT", "FIXED", "DIVISOR"], width=120).pack(side="left", padx=5, pady=(20,0))
        self.create_input(row_r, "RISK (%)", "1.0", width=80, pack_side="left")
        self.create_input(row_r, "DIVISOR", "10000.0", width=120, pack_side="left")
        self.create_input(row_r, "MAX_LOT", "2.0", width=80, pack_side="left")

        prot = self.create_group(left, "> GLOBAL PROTECTION & SAFETY")
        row_p = ctk.CTkFrame(prot, fg_color="transparent")
        row_p.pack(fill="x", padx=10, pady=5)
        self.create_input(row_p, "DAILY_LOSS_USD", "200.0", width=100, pack_side="left")
        self.create_input(row_p, "MAX_POSITIONS", "8", width=100, pack_side="left")

        grid = self.create_group(left, "> ADVANCED LOGIC (GRID/TRAILING)")
        row_g = ctk.CTkFrame(grid, fg_color="transparent")
        row_g.pack(fill="x", padx=10, pady=5)
        self.create_input(row_g, "GRID_MAX_LAYERS", "5", width=100, pack_side="left")
        self.create_input(row_g, "GRID_STEP_PIPS", "200", width=100, pack_side="left")
        self.create_input(row_g, "TRAIL_START", "1.2", width=100, pack_side="left")
        self.create_input(row_g, "TRAIL_STEP", "0.5", width=100, pack_side="left")
        row_g2 = ctk.CTkFrame(grid, fg_color="transparent")
        row_g2.pack(fill="x", padx=10, pady=5)
        for t in ["ENABLE_GRID", "ENABLE_BE", "ENABLE_TRAILING"]:
            ctk.CTkCheckBox(row_g2, text=t, font=ctk.CTkFont(size=10)).pack(side="left", padx=10)

        # Right Symbol Selection
        right = ctk.CTkFrame(main, fg_color=PANEL_BG, width=280)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        ctk.CTkLabel(right, text="> SYMBOL_SELECTION", text_color=ACCENT_YELLOW, font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=15, pady=10)
        ctk.CTkEntry(right, placeholder_text="/ FILTER PAIRS...", fg_color="#0a0a0a").pack(fill="x", padx=15, pady=5)
        sym_list = ctk.CTkScrollableFrame(right, fg_color="transparent")
        sym_list.pack(fill="both", expand=True)
        for s in ["BTCUSDc", "EURUSDc", "USDJPYc", "XAUUSDc", "GBPUSDc", "ETHUSDc"]:
            cb = ctk.CTkCheckBox(sym_list, text=s, font=ctk.CTkFont(size=11))
            cb.pack(anchor="w", padx=10, pady=5)
            if s in ["BTCUSDc", "EURUSDc", "XAUUSDc"]: cb.select()

    def create_group(self, parent, title):
        f = ctk.CTkFrame(parent, fg_color=PANEL_BG, corner_radius=4)
        f.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(f, text=title, text_color=ACCENT_YELLOW, font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=10, pady=5)
        return f

    def create_input(self, parent, label, default, width=200, pack_side="top"):
        c = ctk.CTkFrame(parent, fg_color="transparent")
        c.pack(side=pack_side, padx=10, pady=5, anchor="w")
        ctk.CTkLabel(c, text="> "+label, font=ctk.CTkFont(size=9, weight="bold"), text_color=TEXT_GRAY).pack(anchor="w")
        e = ctk.CTkEntry(c, width=width, fg_color="black", border_color="#333333", height=28)
        e.insert(0, default)
        e.pack()

class MT5LoginWindow(ctk.CTk):
    def __init__(self, on_success):
        super().__init__()
        self.on_success = on_success
        self.title("MT5 Broker Login")
        self.geometry("480x680")
        self.configure(fg_color="#1a1a1a")
        self.resizable(False, False)
        
        ctk.CTkLabel(self, text="BROKER LOGIN", font=ctk.CTkFont(size=28, weight="bold"), text_color=TEXT_WHITE).pack(pady=(60, 40))
        
        self.create_label("Broker Preset:")
        self.preset = ctk.CTkComboBox(self, values=["Exness-Trial", "Exness-Real"], width=380, height=45, fg_color=INPUT_BG)
        self.preset.pack(pady=(0, 20))
        
        self.create_label("Account Number:")
        self.acc = ctk.CTkEntry(self, placeholder_text="159976224", width=380, height=45, fg_color=INPUT_BG)
        self.acc.pack(pady=(0, 20))
        self.acc.insert(0, "159976224")
        
        self.create_label("Password:")
        row_p = ctk.CTkFrame(self, fg_color="transparent")
        row_p.pack(pady=(0, 20))
        self.pwd = ctk.CTkEntry(row_p, placeholder_text="Password", show="*", width=300, height=45, fg_color=INPUT_BG)
        self.pwd.pack(side="left")
        self.show = ctk.CTkCheckBox(row_p, text="Show", font=ctk.CTkFont(size=12), width=20, command=self.toggle)
        self.show.pack(side="left", padx=10)
        
        self.create_label("Server Name:")
        self.srv = ctk.CTkEntry(self, placeholder_text="Exness-MT5Real20", width=380, height=45, fg_color=INPUT_BG)
        self.srv.pack(pady=(0, 20))
        self.srv.insert(0, "Exness-MT5Real20")
        
        self.rem = ctk.CTkCheckBox(self, text="Remember Password", font=ctk.CTkFont(size=13))
        self.rem.pack(pady=(10, 30))
        self.rem.select()
        
        self.btn = ctk.CTkButton(self, text="CONNECT TO MT5", fg_color=ACCENT_GREEN, hover_color="#00a000", 
                                  text_color=TEXT_WHITE, font=ctk.CTkFont(size=18, weight="bold"), height=65, width=400, command=self.submit)
        self.btn.pack(pady=10)

    def create_label(self, t):
        ctk.CTkLabel(self, text=t, font=ctk.CTkFont(size=13), text_color=TEXT_GRAY).pack(anchor="w", padx=50)

    def toggle(self): self.pwd.configure(show="" if self.show.get() else "*")

    def submit(self):
        acc_val = self.acc.get()
        self.destroy()
        self.on_success({"account": acc_val})

class MainApp(ctk.CTk):
    def __init__(self, creds):
        super().__init__()
        self.title("DICKY 2K // PROFESSIONAL TRADING SUITE v1.2.7")
        self.geometry("1280x800")
        self.configure(fg_color="#0a0a0a")
        
        # Header Info Bar
        top = ctk.CTkFrame(self, height=40, fg_color="black", corner_radius=0)
        top.pack(side="top", fill="x")
        ctk.CTkLabel(top, text="DICKY 2K // PROFESSIONAL TRADING SUITE v1.2.7", font=ctk.CTkFont(size=10, weight="bold"), text_color=TEXT_GRAY).pack(side="left", padx=15)
        ctk.CTkLabel(top, text=f"ACCT {creds.get('account')}   SRV ● ONLINE   LATENCY 12ms   UTC {datetime.utcnow().strftime('%H:%M:%S')}", font=ctk.CTkFont(size=10), text_color=TEXT_GRAY).pack(side="right", padx=15)

        # Nav
        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.pack(fill="x", padx=15, pady=10)
        self.btn1 = ctk.CTkButton(nav, text="[F1] DASHBOARD", fg_color=ACCENT_YELLOW, text_color="black", command=self.show_dash)
        self.btn1.pack(side="left", padx=5)
        self.btn2 = ctk.CTkButton(nav, text="[F2] SYSTEM SETTINGS", fg_color="#242424", text_color="white", command=self.show_sett)
        self.btn2.pack(side="left", padx=5)

        self.dash = DashboardView(self, self)
        self.sett = SettingsView(self)
        self.show_dash()

    def show_dash(self): self.sett.pack_forget(); self.dash.pack(fill="both", expand=True, padx=15); self.btn1.configure(fg_color=ACCENT_YELLOW, text_color="black"); self.btn2.configure(fg_color="#242424", text_color="white")
    def show_sett(self): self.dash.pack_forget(); self.sett.pack(fill="both", expand=True, padx=15); self.btn2.configure(fg_color=ACCENT_YELLOW, text_color="black"); self.btn1.configure(fg_color="#242424", text_color="white")

if __name__ == "__main__":
    def run(c): MainApp(c).mainloop()
    MT5LoginWindow(run).mainloop()
