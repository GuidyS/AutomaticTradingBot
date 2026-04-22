import os
import subprocess
import customtkinter

def build():
    # Get customtkinter path
    ctk_path = os.path.dirname(customtkinter.__file__)
    
    # Setup PyInstaller command
    cmd = [
        "python", "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",  # Create a single executable
        "--windowed", # Hide console window
        "--name", "Dicky2K_v1.2.7",
        "--paths", ".", # Explicitly include current directory
        # Bundle necessary files as data
        "--add-data", f"{ctk_path};customtkinter",
        "--add-data", "trader.py;.",
        "--add-data", "config.py;.",
        "--add-data", "database.py;.",
        "--add-data", "analyze_trades.py;.",
        "gui_standalone.py"
    ]
    
    print("Building standalone executable...")
    print("Command:", " ".join(cmd))
    
    subprocess.run(cmd, check=True)
    print("Build complete! Check the 'dist' folder.")

if __name__ == "__main__":
    build()
