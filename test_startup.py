
import sys
try:
    print("Starting import test...")
    import customtkinter as ctk
    import tkinter as tk
    print("Imports successful.")
    
    print("Creating CTk instance...")
    app = ctk.CTk()
    app.withdraw() # Don't show window
    print("CTk instance created successfully.")
    
    print("Test passed.")
    sys.exit(0)
except Exception as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
