import os
import subprocess
import shutil

def run_command(command, msg):
    print(f"\n>>> {msg}...")
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in process.stdout:
        print(line, end='')
    process.wait()
    return process.returncode == 0

def build():
    project_root = os.getcwd()
    dist_dir = os.path.join(project_root, "dist_final")
    
    print("Preparing build directory...")
    # Don't fail if we can't delete, just try
    try:
        if os.path.exists("build"): shutil.rmtree("build")
    except: pass

    # Standard PyInstaller Build (No PyArmor)
    # --onefile: single EXE
    # --noconsole: no terminal
    # --collect-all customtkinter: necessary for some UI elements
    # --distpath: use a fresh folder to avoid locks
    
    pyinstaller_cmd = (
        f'python -m PyInstaller --onefile --noconsole '
        f'--name "Dicky2K_Pro" '
        f'--collect-all customtkinter '
        f'--paths Program '
        f'--distpath "{dist_dir}" '
        f'Program/gui_app.py'
    )
    
    if run_command(pyinstaller_cmd, "Building FINAL PREMIUM EXE with PyInstaller"):
        print("\n" + "="*50)
        print(f"SUCCESS! Dicky2K_Pro.exe is ready in '{dist_dir}' folder.")
        print("="*50)
    else:
        print("\n!!! ERROR: Build failed.")

if __name__ == "__main__":
    build()
