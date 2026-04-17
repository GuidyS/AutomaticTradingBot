import os
import subprocess
import shutil
import sys

def run_command(command, msg):
    print(f"\n>>> {msg}...")
    print(f"Executing: {command}")
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in process.stdout:
        print(line, end='')
    process.wait()
    if process.returncode != 0:
        print(f"\n!!! ERROR: {msg} failed with exit code {process.returncode}")
        return False
    return True

def build():
    # 1. Setup paths
    project_root = os.getcwd()
    program_dir = os.path.join(project_root, "Program")
    obf_dir = os.path.join(project_root, "obfuscated_build")
    dist_dir = os.path.join(project_root, "dist")
    
    # 2. Cleanup old builds
    print("Cleaning up old build artifacts...")
    for d in [obf_dir, dist_dir, "build"]:
        if os.path.exists(d):
            shutil.rmtree(d)

    # 3. Obfuscate using PyArmor
    # We use 'pyarmor gen' for PyArmor 8.0+
    # -r means recursive (obfuscate all files in the directory)
    pyarmor_cmd = f'python -m pyarmor.cli gen -O obfuscated_build -r Program/'
    if not run_command(pyarmor_cmd, "Obfuscating all code in Program/ directory"):
        return

    # 5. Build EXE with PyInstaller
    # Temporarily removing --noconsole to allow debugging if it fails
    pyinstaller_cmd = (
        f'python -m PyInstaller --onefile '
        f'--name "Dicky2K" '
        f'--collect-all customtkinter '
        f'--paths obfuscated_build '
        f'obfuscated_build/gui_app.py'
    )
    
    if not run_command(pyinstaller_cmd, "Building EXE with PyInstaller"):
        return

    print("\n" + "="*50)
    print("SUCCESS! Dicky2K.exe has been generated in the 'dist' folder.")
    print("="*50)

if __name__ == "__main__":
    if not os.path.exists("Program/gui_app.py"):
        print("Error: Could not find Program/gui_app.py. Please run from project root.")
    else:
        build()
