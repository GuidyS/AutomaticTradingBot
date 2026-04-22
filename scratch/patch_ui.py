import re
import os

gui_files = [
    r"c:\Users\HeyBo\Desktop\AutomaticTradingBot-main\Dicky2K_Grid\gui_main.py",
    r"c:\Users\HeyBo\Desktop\AutomaticTradingBot-main\gui_main.py"
]

NEW_DASHBOARD_VIEW = """import sys
import threading
import io
import time

class OutputRedirector(io.StringIO):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
    def write(self, string):
        if string.strip():
            self.callback(string.strip())
    def flush(self):
        pass

class DashboardView(ctk.CTkFrame):
    def __init__(self, master, app_main):
        super().__init__(master, fg_color="transparent")
        self.app_main = app_main
        self.bot_thread = None
        self.bot_running = False
        
        # Top Stats Row
        self.stats_frame = ctk.CTkFrame(self, height=80, fg_color="transparent")
        self.stats_frame.pack(side="top", fill="x", pady=(0, 10))
        
        self.create_stat_box(self.stats_frame, "BALANCE", "$0.00").pack(side="left", fill="both", expand=True, padx=2)
        self.create_stat_box(self.stats_frame, "EQUITY", "$0.00").pack(side="left", fill="both", expand=True, padx=2)
        self.create_stat_box(self.stats_frame, "FLOATING P&L", "+$0.00", color=ACCENT_GREEN).pack(side="left", fill="both", expand=True, padx=2)
        self.create_stat_box(self.stats_frame, "DRAWDOWN", "0.00%", color=ACCENT_YELLOW).pack(side="left", fill="both", expand=True, padx=2)
        self.create_stat_box(self.stats_frame, "WIN RATE", "0.0%", color=ACCENT_GREEN).pack(side="left", fill="both", expand=True, padx=2)
        self.create_stat_box(self.stats_frame, "OPEN POS", "0").pack(side="left", fill="both", expand=True, padx=2)

        # Middle Content Layout: Left (Control + Log), Right (AI + Pos + Risk)
        self.middle_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.middle_frame.pack(side="top", fill="both", expand=True)

        # Left Column
        self.left_col = ctk.CTkFrame(self.middle_frame, fg_color="transparent")
        self.left_col.pack(side="left", fill="both", expand=True, padx=(0, 5))

        # Bot Control
        self.control_frame = ctk.CTkFrame(self.left_col, fg_color=PANEL_BG)
        self.control_frame.pack(side="top", fill="x", pady=(0, 10))
        ctk.CTkLabel(self.control_frame, text="> BOT_CONTROL", text_color=ACCENT_YELLOW, anchor="w", font=ctk.CTkFont(weight="bold")).pack(fill="x", padx=10, pady=5)
        
        ctrl_inner = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        ctrl_inner.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(ctrl_inner, text="STRATEGY: DICKY-CORE-4", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray").pack(side="left", padx=10)
        
        btn_frame = ctk.CTkFrame(ctrl_inner, fg_color="transparent")
        btn_frame.pack(side="left", padx=20)
        
        self.start_btn = ctk.CTkButton(btn_frame, text="▶ START BOT", fg_color="transparent", border_color=ACCENT_YELLOW, border_width=1, text_color=ACCENT_YELLOW, hover_color="#332800", width=160, command=self.start_bot)
        self.start_btn.pack(side="top", pady=2)
        self.emergency_btn = ctk.CTkButton(btn_frame, text="⚠ EMERGENCY CLOSE", fg_color="#330000", border_color=ACCENT_RED, border_width=1, text_color=ACCENT_RED, hover_color="#440000", width=160, command=self.stop_bot)
        self.emergency_btn.pack(side="top", pady=2)

        # Log Window
        self.log_frame = ctk.CTkFrame(self.left_col, fg_color=PANEL_BG)
        self.log_frame.pack(side="top", fill="both", expand=True)
        ctk.CTkLabel(self.log_frame, text="> REAL_TIME_ACTIVITY_LOG", text_color=ACCENT_YELLOW, anchor="w", font=ctk.CTkFont(weight="bold")).pack(fill="x", padx=10, pady=5)
        self.log_text = ctk.CTkTextbox(self.log_frame, fg_color="black", text_color="white", font=ctk.CTkFont(family="Courier", size=11))
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.log_text.insert("0.0", "[System] Ready.\\n")

        # Right Column
        self.right_col = ctk.CTkFrame(self.middle_frame, fg_color="transparent", width=250)
        self.right_col.pack(side="right", fill="y", padx=(5, 0))
        self.right_col.pack_propagate(False)

        # AI Engine
        self.ai_frame = ctk.CTkFrame(self.right_col, fg_color=PANEL_BG)
        self.ai_frame.pack(side="top", fill="x", pady=(0, 10))
        ctk.CTkLabel(self.ai_frame, text="> AI_ENGINE", text_color=ACCENT_YELLOW, anchor="w", font=ctk.CTkFont(weight="bold")).pack(fill="x", padx=10, pady=5)
        
        ai_inner = ctk.CTkFrame(self.ai_frame, fg_color="transparent")
        ai_inner.pack(fill="x", padx=10, pady=5)
        
        # MODEL
        model_row = ctk.CTkFrame(ai_inner, fg_color="transparent")
        model_row.pack(fill="x", pady=2)
        ctk.CTkLabel(model_row, text="MODEL", font=ctk.CTkFont(size=10), text_color="gray").pack(side="left")
        ctk.CTkLabel(model_row, text="llama3.2", font=ctk.CTkFont(size=10, weight="bold")).pack(side="right")
        
        # GEMINI / OLLAMA Status
        status_row = ctk.CTkFrame(ai_inner, fg_color="transparent")
        status_row.pack(fill="x", pady=10)
        ctk.CTkLabel(status_row, text="🔴 GEMINI", font=ctk.CTkFont(size=10, weight="bold"), text_color="#cc0000").pack(side="left")
        ctk.CTkLabel(status_row, text="🟢 OLLAMA", font=ctk.CTkFont(size=10, weight="bold"), text_color="#00cc00").pack(side="right")
        
        # BIAS
        bias_row = ctk.CTkFrame(ai_inner, fg_color="transparent")
        bias_row.pack(fill="x", pady=2)
        ctk.CTkLabel(bias_row, text="BIAS", font=ctk.CTkFont(size=10), text_color="gray").pack(side="left")
        ctk.CTkLabel(bias_row, text="SCAN...", font=ctk.CTkFont(size=10, weight="bold")).pack(side="right")
        
        # CONF
        conf_row = ctk.CTkFrame(ai_inner, fg_color="transparent")
        conf_row.pack(fill="x", pady=2)
        ctk.CTkLabel(conf_row, text="CONF", font=ctk.CTkFont(size=10), text_color="gray").pack(side="left")
        ctk.CTkLabel(conf_row, text="0.00", font=ctk.CTkFont(size=10, weight="bold")).pack(side="right")

        # Positions
        self.pos_frame = ctk.CTkFrame(self.right_col, fg_color=PANEL_BG)
        self.pos_frame.pack(side="top", fill="both", expand=True, pady=(0, 10))
        ctk.CTkLabel(self.pos_frame, text="> POSITIONS", text_color=ACCENT_YELLOW, anchor="w", font=ctk.CTkFont(weight="bold")).pack(fill="x", padx=10, pady=5)
        self.pos_list = ctk.CTkTextbox(self.pos_frame, fg_color="black", text_color="gray", font=ctk.CTkFont(size=10))
        self.pos_list.pack(fill="both", expand=True, padx=10, pady=10)
        self.pos_list.insert("0.0", "          - NO OPEN POSITIONS -")

        # Risk Monitor
        self.risk_mon_frame = ctk.CTkFrame(self.right_col, fg_color=PANEL_BG)
        self.risk_mon_frame.pack(side="top", fill="x")
        ctk.CTkLabel(self.risk_mon_frame, text="> RISK_MONITOR", text_color=ACCENT_YELLOW, anchor="w", font=ctk.CTkFont(weight="bold")).pack(fill="x", padx=10, pady=5)
        
        exp_row = ctk.CTkFrame(self.risk_mon_frame, fg_color="transparent")
        exp_row.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(exp_row, text="EXPOSURE", font=ctk.CTkFont(size=10), text_color="gray").pack(side="left")
        ctk.CTkLabel(exp_row, text="0%", font=ctk.CTkFont(size=10, weight="bold")).pack(side="right")

        # Bottom Status Bar
        self.status_bar = ctk.CTkFrame(self, height=30, fg_color="transparent")
        self.status_bar.pack(side="bottom", fill="x", pady=(5, 0))
        ctk.CTkLabel(self.status_bar, text="● STATUS: OFFLINE", text_color="gray", font=ctk.CTkFont(size=10, weight="bold")).pack(side="left", padx=10)
        ctk.CTkLabel(self.status_bar, text="MODE LIVE", text_color=ACCENT_YELLOW, font=ctk.CTkFont(size=10, weight="bold")).pack(side="left", padx=10)
        ctk.CTkLabel(self.status_bar, text="MEM 80.5% CPU 61.3%", text_color="gray", font=ctk.CTkFont(size=10)).pack(side="right", padx=10)

    def create_stat_box(self, parent, title, value, color="white"):
        frame = ctk.CTkFrame(parent, fg_color=PANEL_BG)
        ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=10, weight="bold"), text_color="gray").pack(pady=(10, 0))
        ctk.CTkLabel(frame, text=value, font=ctk.CTkFont(size=20, weight="bold"), text_color=color).pack(pady=(0, 10))
        return frame

    def log_message(self, msg):
        self.log_text.insert("end", msg + "\\n")
        self.log_text.see("end")

    def start_bot(self):
        if self.bot_running:
            self.log_message("[System] Bot is already running!")
            return
            
        self.log_message("[System] Starting Bot Process...")
        self.start_btn.configure(text="■ STOP BOT", fg_color="transparent", border_color=ACCENT_YELLOW, text_color=ACCENT_YELLOW, command=self.stop_bot)
        self.bot_running = True
        
        self.bot_thread = threading.Thread(target=self.run_trader_process, daemon=True)
        self.bot_thread.start()

    def run_trader_process(self):
        try:
            # We import trader dynamically so PyInstaller packages it
            import trader
            
            # Redirect stdout to GUI log
            old_stdout = sys.stdout
            sys.stdout = OutputRedirector(lambda s: self.after(0, self.log_message, s))
            
            self.ea_instance = trader.SelfLearningEA()
            
            # Run bot loop (we assume it checks a flag or runs indefinitely)
            # To allow graceful stop, we could monkey patch its loop condition
            # but for now we just call run()
            self.ea_instance.run()
            
        except Exception as e:
            self.after(0, self.log_message, f"❌ Bot Error: {e}")
        finally:
            sys.stdout = old_stdout
            self.after(0, self.log_message, "[System] Bot process ended.")
            self.after(0, lambda: self.start_btn.configure(text="▶ START BOT", fg_color="transparent", command=self.start_bot))
            self.bot_running = False

    def stop_bot(self):
        self.log_message("[System] Stopping bot...")
        # Since we run EA in a thread, we might need a flag in trader.py to stop it cleanly
        # For now, we simulate a stop message or interrupt
        if hasattr(self, 'ea_instance'):
            # Just a hack if trader.py has a stop flag
            self.ea_instance.running = False 
        self.bot_running = False
        self.start_btn.configure(text="▶ START BOT", fg_color="transparent", command=self.start_bot)
"""

NEW_SETTINGS_VIEW = """class SettingsView(ctk.CTkScrollableFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        
        self.inputs = {}
        self.checkboxes = {}
        self.comboboxes = {}
        
        # Load existing settings if any
        self.loaded_settings = {}
        import json
        if os.path.exists("settings.json"):
            try:
                with open("settings.json", "r", encoding="utf-8") as f:
                    self.loaded_settings = json.load(f)
            except Exception:
                pass
        
        # --- Form Sections ---
        self.create_section_title("# SYSTEM / CONFIGURATION")
        
        # 1. AI ENGINE
        ai_frame = self.create_group("> AI_ENGINE & CONNECTIVITY")
        ai_row1 = ctk.CTkFrame(ai_frame, fg_color="transparent")
        ai_row1.pack(fill="x", padx=10, pady=5)
        self.create_checkbox(ai_row1, "ENABLE_AI_TRADING_MODE")
        self.create_checkbox(ai_row1, "ENABLE_OLLAMA_FALLBACK")
        self.create_checkbox(ai_row1, "ENABLE_AGGRESSIVE_AI_ENTRY")
        
        ai_row2 = ctk.CTkFrame(ai_frame, fg_color="transparent")
        ai_row2.pack(fill="x", padx=10, pady=5)
        self.create_input(ai_row2, "GEMINI_PRO_API_KEY", width=400, pack_side="left")
        self.create_input(ai_row2, "AI_CONFIDENCE_THRESHOLD", "70", pack_side="left")
        
        ollama_row = ctk.CTkFrame(ai_frame, fg_color="transparent")
        ollama_row.pack(fill="x", padx=10, pady=5)
        self.create_input(ollama_row, "OLLAMA_URL", "http://localhost:11434", pack_side="left")
        
        c_var = ctk.StringVar(value=self.loaded_settings.get("OLLAMA_MODEL", "llama3.2"))
        cb = ctk.CTkComboBox(ollama_row, values=["llama3.1", "llama3.2"], variable=c_var)
        cb.pack(side="left", padx=10, pady=(20,0))
        self.comboboxes["OLLAMA_MODEL"] = c_var
        
        ctk.CTkButton(ollama_row, text="↻ REFRESH", width=80, fg_color=ACCENT_YELLOW, text_color="black").pack(side="left", pady=(20,0))

        # Bottom AI Connectivity Status
        ai_bottom = ctk.CTkFrame(ai_frame, fg_color="transparent")
        ai_bottom.pack(fill="x", padx=10, pady=(15, 10))
        ctk.CTkLabel(ai_bottom, text="🔴 GEMINI: NO API KEY", font=ctk.CTkFont(size=10, weight="bold"), text_color="#cc0000").pack(side="left", padx=(0, 20))
        ctk.CTkLabel(ai_bottom, text="🟢 OLLAMA: ONLINE", font=ctk.CTkFont(size=10, weight="bold"), text_color="#00cc00").pack(side="left")
        ctk.CTkButton(ai_bottom, text="TEST AI CONNECTIONS", fg_color="transparent", border_color=ACCENT_YELLOW, border_width=1, hover_color="#332800", text_color="white").pack(side="right")

        # 2. TELEGRAM
        tg_frame = self.create_group("> TELEGRAM_NOTIFICATIONS")
        self.create_checkbox(tg_frame, "ENABLE_TELEGRAM_ALERTS")
        tg_row = ctk.CTkFrame(tg_frame, fg_color="transparent")
        tg_row.pack(fill="x", padx=10, pady=5)
        self.create_input(tg_row, "BOT_TOKEN", width=300, pack_side="left")
        self.create_input(tg_row, "CHAT_ID", width=200, pack_side="left")

        # 3. RISK MANAGEMENT
        risk_frame = self.create_group("> RISK & MONEY MANAGEMENT")
        risk_row = ctk.CTkFrame(risk_frame, fg_color="transparent")
        risk_row.pack(fill="x", padx=10, pady=10)
        
        # LOT MODE Select
        lot_mode_col = ctk.CTkFrame(risk_row, fg_color="transparent")
        lot_mode_col.pack(side="left", padx=(0, 20), anchor="w")
        ctk.CTkLabel(lot_mode_col, text="LOT_MODE", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray").pack(anchor="w")
        self.lot_mode_var = ctk.StringVar(value=self.loaded_settings.get("RISK_MODE", "PERCENT"))
        self.lot_cb = ctk.CTkComboBox(lot_mode_col, values=["PERCENT", "FIXED", "DIVISOR"], variable=self.lot_mode_var, command=self.update_lot_labels)
        self.lot_cb.pack(anchor="w")
        
        # Dynamic Risk/Fixed field
        self.risk_col = ctk.CTkFrame(risk_row, fg_color="transparent")
        self.risk_col.pack(side="left", padx=(0, 20), anchor="w")
        self.risk_lbl = ctk.CTkLabel(self.risk_col, text="> RISK (%)", font=ctk.CTkFont(size=10, weight="bold"), text_color=ACCENT_YELLOW)
        self.risk_lbl.pack(anchor="w")
        self.risk_entry = ctk.CTkEntry(self.risk_col, width=140, fg_color="black", border_color="#333333")
        self.risk_entry.pack(anchor="w")
        
        # Dynamic Divisor field
        self.div_col = ctk.CTkFrame(risk_row, fg_color="transparent")
        self.div_col.pack(side="left", padx=(0, 20), anchor="w")
        self.div_lbl = ctk.CTkLabel(self.div_col, text="> DIVISOR (DISABLED)", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray")
        self.div_lbl.pack(anchor="w")
        self.div_entry = ctk.CTkEntry(self.div_col, width=140, fg_color="black", border_color="#333333")
        self.div_entry.pack(anchor="w")
        
        # Initialize values
        if self.lot_mode_var.get() == "PERCENT":
            self.risk_entry.insert(0, str(self.loaded_settings.get("RISK_PERCENT", "1.0")))
        elif self.lot_mode_var.get() == "FIXED":
            self.risk_entry.insert(0, str(self.loaded_settings.get("FIXED_LOT", "0.02")))
        self.div_entry.insert(0, str(self.loaded_settings.get("LOT_DIVISOR", "10000.0")))
        
        # Max Lot Field
        self.max_lot_col = ctk.CTkFrame(risk_row, fg_color="transparent")
        self.max_lot_col.pack(side="left", anchor="w")
        ctk.CTkLabel(self.max_lot_col, text="> MAX_LOT", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray").pack(anchor="w")
        self.max_lot_entry = ctk.CTkEntry(self.max_lot_col, width=140, fg_color="black", border_color="#333333")
        self.max_lot_entry.insert(0, str(self.loaded_settings.get("MAX_LOT", "2.0")))
        self.max_lot_entry.pack(anchor="w")
        
        # Run label update initially
        self.update_lot_labels(self.lot_mode_var.get())
        
        risk_row2 = ctk.CTkFrame(risk_frame, fg_color="transparent")
        risk_row2.pack(fill="x", padx=10, pady=5)
        self.create_input(risk_row2, "MIN_LOT", "0.02", pack_side="left")
        self.create_input(risk_row2, "MAX_DAILY_LOSS_USD", "200.0", pack_side="left")

        # 4. ADVANCED LOGIC (GRID)
        grid_frame = self.create_group("> ADVANCED LOGIC (GRID/TRAILING)")
        grid_check_row = ctk.CTkFrame(grid_frame, fg_color="transparent")
        grid_check_row.pack(fill="x", padx=10, pady=5)
        self.create_checkbox(grid_check_row, "ENABLE_GRID")
        self.create_checkbox(grid_check_row, "ENABLE_MARTINGALE")
        self.create_checkbox(grid_check_row, "ENABLE_TRAILING")
        self.create_checkbox(grid_check_row, "ENABLE_HEDGE")

        grid_row = ctk.CTkFrame(grid_frame, fg_color="transparent")
        grid_row.pack(fill="x", padx=10, pady=5)
        self.create_input(grid_row, "GRID_MAX_LAYERS", "5", pack_side="left")
        self.create_input(grid_row, "GRID_STEP_PIPS", "200", pack_side="left")
        self.create_input(grid_row, "TRAIL_START", "1.2", pack_side="left")
        self.create_input(grid_row, "TRAIL_STEP", "0.5", pack_side="left")
        
        mart_row = ctk.CTkFrame(grid_frame, fg_color="transparent")
        mart_row.pack(fill="x", padx=10, pady=5)
        self.create_input(mart_row, "MART_MAX_LEVEL", "3", pack_side="left")
        self.create_input(mart_row, "MART_LOT_MULTIPLIER", "1.5", pack_side="left")

        # 5. GENERAL & FILTERS
        filter_frame = self.create_group("> GENERAL & FILTERS")
        filter_row = ctk.CTkFrame(filter_frame, fg_color="transparent")
        filter_row.pack(fill="x", padx=10, pady=5)
        self.create_input(filter_row, "ACTIVE_SYMBOL", "XAUUSDc", pack_side="left")
        self.create_input(filter_row, "MAGIC_NUMBER", "20250415", pack_side="left")
        self.create_input(filter_row, "MIN_RR_RATIO", "1.2", pack_side="left")
        
        filter_row2 = ctk.CTkFrame(filter_frame, fg_color="transparent")
        filter_row2.pack(fill="x", padx=10, pady=5)
        self.create_checkbox(filter_row2, "ENABLE_NEWS_FILTER")
        self.create_checkbox(filter_row2, "ENABLE_MULTI_TP")
        self.create_input(filter_row2, "TRADE_TIME_START", "0", pack_side="left")
        self.create_input(filter_row2, "TRADE_TIME_END", "23", pack_side="left")

        # Save Button
        save_frame = ctk.CTkFrame(self, fg_color="transparent")
        save_frame.pack(fill="x", pady=20)
        self.save_btn = ctk.CTkButton(save_frame, text="▶ SAVE_ALL_CHANGES", fg_color=ACCENT_YELLOW, text_color="black", width=150, font=ctk.CTkFont(weight="bold"), command=self.save_settings)
        self.save_btn.pack(side="right", padx=10)
        ctk.CTkButton(save_frame, text="REVERT", fg_color="#333333", width=100).pack(side="right")

    def update_lot_labels(self, choice):
        if choice == "PERCENT":
            self.risk_lbl.configure(text="> RISK (%)", text_color=ACCENT_YELLOW)
            self.div_lbl.configure(text="> DIVISOR (DISABLED)", text_color="gray")
        elif choice == "FIXED":
            self.risk_lbl.configure(text="> FIXED LOT", text_color=ACCENT_YELLOW)
            self.div_lbl.configure(text="> DIVISOR (DISABLED)", text_color="gray")
        elif choice == "DIVISOR":
            self.risk_lbl.configure(text="> RISK (DISABLED)", text_color="gray")
            self.div_lbl.configure(text="> LOT_DIVISOR", text_color=ACCENT_YELLOW)

    def create_checkbox(self, parent, text):
        default = self.loaded_settings.get(text, False)
        var = ctk.BooleanVar(value=default)
        cb = ctk.CTkCheckBox(parent, text=text, variable=var)
        cb.pack(side="left", padx=(0, 10))
        if parent.__class__.__name__ == "CTkFrame" and parent.master.__class__.__name__ == "SettingsView":
             cb.pack(anchor="w", padx=10, pady=5)
        self.checkboxes[text] = var
        return cb

    def create_section_title(self, text):
        ctk.CTkLabel(self, text=text, font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", pady=(10, 5))

    def create_group(self, title):
        frame = ctk.CTkFrame(self, fg_color=PANEL_BG)
        frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(frame, text=title, text_color=ACCENT_YELLOW, font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=10, pady=5)
        return frame

    def create_input(self, parent, label_text, default="", width=140, pack_side="top"):
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.pack(side=pack_side, padx=(0, 20), pady=(0, 5), anchor="w")
        ctk.CTkLabel(container, text="> " + label_text, font=ctk.CTkFont(size=10, weight="bold"), text_color="gray").pack(anchor="w")
        entry = ctk.CTkEntry(container, width=width, fg_color="black", border_color="#333333")
        
        actual_default = self.loaded_settings.get(label_text, default)
        if actual_default is not None:
            entry.insert(0, str(actual_default))
            
        entry.pack(anchor="w")
        self.inputs[label_text] = entry
        return entry

    def save_settings(self):
        import json
        settings = {}
        for k, entry in self.inputs.items():
            val = entry.get()
            try:
                if "." in val: val = float(val)
                else: val = int(val)
            except ValueError: pass
            if val == "True": val = True
            if val == "False": val = False
            settings[k] = val
            
        for k, var in self.checkboxes.items():
            settings[k] = var.get()
            
        for k, var in self.comboboxes.items():
            settings[k] = var.get()
            
        mode = self.lot_mode_var.get()
        settings["RISK_MODE"] = mode
        try: risk_val = float(self.risk_entry.get())
        except: risk_val = 0.0
        try: div_val = float(self.div_entry.get())
        except: div_val = 10000.0
        try: max_lot_val = float(self.max_lot_entry.get())
        except: max_lot_val = 2.0
        
        if mode == "PERCENT": settings["RISK_PERCENT"] = risk_val
        elif mode == "FIXED": settings["FIXED_LOT"] = risk_val
        settings["LOT_DIVISOR"] = div_val
        settings["MAX_LOT"] = max_lot_val
        
        with open("settings.json", "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4)
            
        self.save_btn.configure(text="✔ SAVED!", fg_color="#00cc00")
        self.after(2000, lambda: self.save_btn.configure(text="▶ SAVE_ALL_CHANGES", fg_color=ACCENT_YELLOW))
"""

for filepath in gui_files:
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        # We need to remove imports at the top if we redefine them, but 'import threading' etc is fine
        idx_dash = content.find("class DashboardView(ctk.CTkFrame):")
        idx_set = content.find("class SettingsView(ctk.CTkScrollableFrame):")
        
        if idx_dash != -1 and idx_set != -1:
            part1 = content[:idx_dash]
            end_idx = content.find("if __name__ == \"__main__\":", idx_set)
            
            new_content = part1 + NEW_DASHBOARD_VIEW + "\\n" + NEW_SETTINGS_VIEW + "\\n"
            if end_idx != -1:
                new_content += content[end_idx:]
                
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Patched {filepath}")
