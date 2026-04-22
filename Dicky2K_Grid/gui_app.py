import customtkinter as ctk
from gui_login import MT5LoginWindow
from gui_main import MainApplication

def on_login_success(credentials):
    # This function is called when the login window successfully "connects"
    print(f"Login successful for account: {credentials['account']}")
    
    # Initialize and start the main application window
    app = MainApplication(credentials)
    app.mainloop()

if __name__ == "__main__":
    # Ensure customtkinter looks good on Windows
    ctk.set_appearance_mode("dark")
    
    # Start the Login Window first
    login_app = MT5LoginWindow(on_login_success)
    login_app.mainloop()
