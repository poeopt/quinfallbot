import PyInstaller.__main__
import os

def build():
    # Entry point
    script = "bot_core.py"

    # Bundle settings
    params = [
        script,
        "--onefile",
        "--noconsole",
        "--name=QuinfallBot",
        "--add-data=src:src",
    ]

    print(f"Building {script} into EXE...")
    PyInstaller.__main__.run(params)
    print("Build complete. EXE is in 'dist/' directory.")

if __name__ == "__main__":
    build()
