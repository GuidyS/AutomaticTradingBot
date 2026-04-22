import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import json
import os

# --- Theme & Colors ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")
BG_COLOR = "#2b2b2b"
TEXT_COLOR = "#ffffff"
BTN_GREEN = "#008a00"
BTN_GREEN_HOVER = "#006b00"

class MT5LoginWindow(ctk.CTk):
    def __init__(self, on_login_success):
        super().__init__()
        self.on_login_success = on_login_success
        
        self.title("MT5 Broker Login")
        self.geometry("400x550")
        self.configure(fg_color=BG_COLOR)
        self.resizable(False, False)
        
        # Center the window
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry('{}x{}+{}+{}'.format(width, height, x, y))

        # Title Label
        self.title_label = ctk.CTkLabel(self, text="BROKER LOGIN", font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.pack(pady=(30, 20))

        # Broker Preset
        self.preset_label = ctk.CTkLabel(self, text="Broker Preset:", anchor="w")
        self.preset_label.pack(padx=40, pady=(10, 0), fill="x")
        self.preset_var = ctk.StringVar(value="Exness-Trial")
        self.preset_dropdown = ctk.CTkComboBox(self, variable=self.preset_var, values=["Exness-Trial", "Exness-Real"], command=self.on_preset_change)
        self.preset_dropdown.pack(padx=40, pady=(0, 15), fill="x")

        # Account Number
        self.account_label = ctk.CTkLabel(self, text="Account Number:", anchor="w")
        self.account_label.pack(padx=40, pady=(5, 0), fill="x")
        self.account_entry = ctk.CTkEntry(self)
        self.account_entry.pack(padx=40, pady=(0, 15), fill="x")

        # Password Frame (for Entry + Checkbox)
        self.pwd_label = ctk.CTkLabel(self, text="Password:", anchor="w")
        self.pwd_label.pack(padx=40, pady=(5, 0), fill="x")
        
        self.pwd_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.pwd_frame.pack(padx=40, pady=(0, 15), fill="x")
        
        self.pwd_entry = ctk.CTkEntry(self.pwd_frame, show="*")
        self.pwd_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.show_pwd_var = ctk.BooleanVar(value=False)
        self.show_pwd_checkbox = ctk.CTkCheckBox(self.pwd_frame, text="Show", variable=self.show_pwd_var, command=self.toggle_password, width=60)
        self.show_pwd_checkbox.pack(side="right")

        # Server Name
        self.server_label = ctk.CTkLabel(self, text="Server Name:", anchor="w")
        self.server_label.pack(padx=40, pady=(5, 0), fill="x")
        self.server_entry = ctk.CTkEntry(self)
        self.server_entry.insert(0, "Exness-MT5Trial")
        self.server_entry.pack(padx=40, pady=(0, 20), fill="x")

        # Remember Password
        self.remember_var = ctk.BooleanVar(value=False)
        self.remember_checkbox = ctk.CTkCheckBox(self, text="Remember Password", variable=self.remember_var)
        self.remember_checkbox.pack(pady=(5, 20))

        # Connect Button
        self.connect_btn = ctk.CTkButton(self, text="CONNECT TO MT5", fg_color=BTN_GREEN, hover_color=BTN_GREEN_HOVER, font=ctk.CTkFont(size=14, weight="bold"), height=40, command=self.login)
        self.connect_btn.pack(padx=40, pady=(10, 20), fill="x")

        self.load_credentials()

    def on_preset_change(self, choice):
        if choice == "Exness-Trial":
            self.server_entry.delete(0, 'end')
            self.server_entry.insert(0, "Exness-MT5Trial")
        elif choice == "Exness-Real":
            self.server_entry.delete(0, 'end')
            self.server_entry.insert(0, "Exness-MT5Real")

    def toggle_password(self):
        if self.show_pwd_var.get():
            self.pwd_entry.configure(show="")
        else:
            self.pwd_entry.configure(show="*")

    def load_credentials(self):
        try:
            if os.path.exists("login_cache.json"):
                with open("login_cache.json", "r") as f:
                    data = json.load(f)
                    if data.get("remember"):
                        self.account_entry.insert(0, data.get("account", ""))
                        self.pwd_entry.insert(0, data.get("password", ""))
                        self.server_entry.delete(0, 'end')
                        self.server_entry.insert(0, data.get("server", ""))
                        self.preset_var.set(data.get("preset", "Exness-Trial"))
                        self.remember_var.set(True)
        except Exception:
            pass

    def save_credentials(self, account, password, server, preset):
        if self.remember_var.get():
            data = {
                "account": account,
                "password": password,
                "server": server,
                "preset": preset,
                "remember": True
            }
            with open("login_cache.json", "w") as f:
                json.dump(data, f)
        else:
            if os.path.exists("login_cache.json"):
                os.remove("login_cache.json")

    def login(self):
        account = self.account_entry.get().strip()
        password = self.pwd_entry.get().strip()
        server = self.server_entry.get().strip()
        preset = self.preset_var.get()

        if not account or not password or not server:
            messagebox.showerror("Error", "Please fill in all fields")
            return
        
        self.save_credentials(account, password, server, preset)
        
        # Here we would normally connect to MT5.
        # For now, we simulate a successful login and pass the credentials to the main window.
        credentials = {
            "account": account,
            "password": password,
            "server": server
        }
        self.destroy() # Close login window
        self.on_login_success(credentials)

if __name__ == "__main__":
    def dummy_success(creds):
        print(f"Logged in with: {creds}")
    app = MT5LoginWindow(dummy_success)
    app.mainloop()
