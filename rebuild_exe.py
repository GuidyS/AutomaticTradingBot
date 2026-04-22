
import os
import subprocess
import shutil

def rebuild():
    # 1. Clean up
    for d in ["build", "dist", "dist_final"]:
        if os.path.exists(d):
            shutil.rmtree(d)
    
    # 2. Build command
    entry_point = "Dicky2K_Grid/gui_app.py"
    if not os.path.exists(entry_point):
        print(f"Error: {entry_point} not found!")
        return

    # Modern PyInstaller command
    cmd = [
        "python", "-m", "PyInstaller",
        "--onefile",
        "--noconsole", 
        "--name", "Dicky2K_Pro_v1.2.7",
        "--collect-all", "customtkinter",
        "--add-data", "Dicky2K_Grid/gui_main.py;.",
        "--add-data", "Dicky2K_Grid/gui_login.py;.",
        "--add-data", "Dicky2K_Grid/trader.py;.",
        "--add-data", "Dicky2K_Grid/config.py;.",
        "--add-data", "Dicky2K_Grid/database.py;.",
        "--add-data", "Dicky2K_Grid/analyze_trades.py;.",
        "--distpath", "dist_final",
        entry_point
    ]
    
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd)
    
    # Copy settings.json to dist_final for convenience
    if os.path.exists("settings.json"):
        shutil.copy("settings.json", "dist_final/settings.json")
    
    print("\nBuild finished. Check 'dist_final' folder.")

if __name__ == "__main__":
    rebuild()
