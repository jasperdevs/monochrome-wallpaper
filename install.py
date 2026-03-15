import sys
from pathlib import Path

import generate_wallpaper as app


def write_startup_vbs(project_dir: Path):
    startup_dir = Path.home() / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup"
    startup_dir.mkdir(parents=True, exist_ok=True)
    vbs_path = startup_dir / "monochrome-wallpaper.vbs"
    pythonw = Path(sys.executable.replace("python.exe", "pythonw.exe"))
    if not pythonw.exists():
        pythonw = Path(sys.executable)
    script_path = project_dir / "generate_wallpaper.py"
    content = (
        'Set WshShell = CreateObject("WScript.Shell")\r\n'
        f'WshShell.Run Chr(34) & "{str(pythonw)}" & Chr(34) & " " & Chr(34) & "{str(script_path)}" & Chr(34), 0, False\r\n'
    )
    vbs_path.write_text(content, encoding="ascii")
    return vbs_path


def main():
    project_dir = Path(__file__).parent
    vbs = write_startup_vbs(project_dir)
    wall, lock = app.generate_assets(project_dir)
    app.hide_desktop_overlay()
    app.apply_wallpaper(wall)
    app.hide_desktop_overlay()
    lock_ok = app.try_set_lock_screen(lock)
    print(f"startup={vbs}")
    print(f"wallpaper={wall}")
    print(f"lockscreen={lock}")
    print(f"lockscreen_applied={lock_ok}")


if __name__ == "__main__":
    main()
