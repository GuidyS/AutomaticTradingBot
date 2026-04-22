import re
import os

gui_files = [
    r"c:\Users\HeyBo\Desktop\AutomaticTradingBot-main\Dicky2K_Grid\gui_main.py",
    r"c:\Users\HeyBo\Desktop\AutomaticTradingBot-main\gui_main.py"
]

SETTINGS_VIEW_CODE = """class SettingsView(ctk.CTkScrollableFrame):
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
        ai_frame = self.create_group("> AI ENGINE & CONNECTIVITY")
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
        
        c_var = ctk.StringVar(value=self.loaded_settings.get("OLLAMA_MODEL", "llama3.1"))
        cb = ctk.CTkComboBox(ollama_row, values=["llama3.1", "llama3.2"], variable=c_var)
        cb.pack(side="left", padx=10, pady=(20,0))
        self.comboboxes["OLLAMA_MODEL"] = c_var
        
        ctk.CTkButton(ollama_row, text="↻ REFRESH", width=80, fg_color=ACCENT_YELLOW, text_color="black").pack(side="left", pady=(20,0))

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
        risk_row.pack(fill="x", padx=10, pady=5)
        
        lot_mode_col = ctk.CTkFrame(risk_row, fg_color="transparent")
        lot_mode_col.pack(side="left", padx=(0, 10))
        ctk.CTkLabel(lot_mode_col, text="LOT_MODE", font=ctk.CTkFont(size=10), text_color=ACCENT_YELLOW).pack(anchor="w")
        
        radio_frame = ctk.CTkFrame(lot_mode_col, fg_color="transparent")
        radio_frame.pack(anchor="w")
        self.lot_mode_var = ctk.StringVar(value=self.loaded_settings.get("RISK_MODE", "FIXED"))
        ctk.CTkRadioButton(radio_frame, text="PERCENT", variable=self.lot_mode_var, value="PERCENT", font=ctk.CTkFont(size=10)).pack(side="left", padx=(0, 10))
        ctk.CTkRadioButton(radio_frame, text="FIXED", variable=self.lot_mode_var, value="FIXED", font=ctk.CTkFont(size=10)).pack(side="left", padx=(0, 10))
        ctk.CTkRadioButton(radio_frame, text="DIVISOR", variable=self.lot_mode_var, value="DIVISOR", font=ctk.CTkFont(size=10)).pack(side="left")
        
        self.create_input(risk_row, "RISK_PERCENT", "1.0", pack_side="left")
        self.create_input(risk_row, "FIXED_LOT", "0.02", pack_side="left")
        self.create_input(risk_row, "LOT_DIVISOR", "10000.0", pack_side="left")
        
        risk_row2 = ctk.CTkFrame(risk_frame, fg_color="transparent")
        risk_row2.pack(fill="x", padx=10, pady=5)
        self.create_input(risk_row2, "MIN_LOT", "0.02", pack_side="left")
        self.create_input(risk_row2, "MAX_LOT", "2.0", pack_side="left")
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

    def create_checkbox(self, parent, text):
        default = self.loaded_settings.get(text, False)
        var = ctk.BooleanVar(value=default)
        cb = ctk.CTkCheckBox(parent, text=text, variable=var)
        cb.pack(side="left", padx=(0, 10))
        if parent.__class__.__name__ == "CTkFrame" and parent.master.__class__.__name__ == "SettingsView":
             # Special case for TELEGRAM
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
        container.pack(side=pack_side, padx=(0, 10), pady=(0, 5), anchor="w")
        ctk.CTkLabel(container, text=label_text, font=ctk.CTkFont(size=10), text_color=ACCENT_YELLOW).pack(anchor="w")
        entry = ctk.CTkEntry(container, width=width, fg_color="black", border_color="#333333")
        
        # Load from settings if exists
        actual_default = self.loaded_settings.get(label_text, default)
        if actual_default is not None:
            entry.insert(0, str(actual_default))
            
        entry.pack(anchor="w")
        self.inputs[label_text] = entry
        return entry

    def save_settings(self):
        import json
        settings = {}
        # Save inputs
        for k, entry in self.inputs.items():
            val = entry.get()
            # Try convert to number if possible
            try:
                if "." in val:
                    val = float(val)
                else:
                    val = int(val)
            except ValueError:
                pass
            if val == "True": val = True
            if val == "False": val = False
            settings[k] = val
            
        # Save checkboxes
        for k, var in self.checkboxes.items():
            settings[k] = var.get()
            
        # Save comboboxes
        for k, var in self.comboboxes.items():
            settings[k] = var.get()
            
        # Save radio
        settings["RISK_MODE"] = self.lot_mode_var.get()
        
        with open("settings.json", "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4)
            
        self.save_btn.configure(text="✔ SAVED!", fg_color="#00cc00")
        self.after(2000, lambda: self.save_btn.configure(text="▶ SAVE_ALL_CHANGES", fg_color=ACCENT_YELLOW))
"""

for filepath in gui_files:
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Find class SettingsView and replace it to the end
        idx = content.find("class SettingsView(ctk.CTkScrollableFrame):")
        if idx != -1:
            end_idx = content.find("if __name__ == \"__main__\":", idx)
            if end_idx != -1:
                new_content = content[:idx] + SETTINGS_VIEW_CODE + "\n" + content[end_idx:]
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"Patched {filepath}")
            else:
                new_content = content[:idx] + SETTINGS_VIEW_CODE + "\n"
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"Patched {filepath} (no main block)")
