"""
monochrome-wallpaper
Live monochrome system-info wallpaper. 
Terminal aesthetic with box frames, sparklines, and pure data.
No personal data.
"""

import ctypes
import ctypes.wintypes
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import psutil
from PIL import Image, ImageDraw, ImageFont


# ── config ──────────────────────────────────────────────
INTERVAL = 15
TASKBAR_CLEARANCE = 110
FONT_NAME = "CascadiaMono.ttf"
FONT_BOLD = "CascadiaMonoNF-Bold.otf"
FALLBACK_FONT = "consola.ttf"

BG = (16, 16, 16)
GRID = (28, 28, 28)
DIM = (80, 80, 80)
MID = (140, 140, 140)
BRIGHT = (215, 215, 215)
WHITE = (245, 245, 245)
BAR_BG = (30, 30, 30)
ACCENT = (100, 100, 100)

CPU_HISTORY = []
NET_STATE = {"sent": None, "recv": None, "time": None}
PROC_STATE = {}
WEATHER_CACHE = {"data": None, "time": 0}
STATIC_INFO = {}
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)


# ── screen ──────────────────────────────────────────────
def get_screen_size():
    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    except Exception:
        return 1920, 1080


def ps(cmd: str) -> str:
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=NO_WINDOW,
        )
        return result.stdout.strip()
    except Exception:
        return ""


# ── system info ─────────────────────────────────────────
def get_cpu_name():
    if "cpu_name" in STATIC_INFO:
        return STATIC_INFO["cpu_name"]
    name = ps("(Get-CimInstance Win32_Processor | Select-Object -First 1).Name")
    cores = ps("(Get-CimInstance Win32_Processor | Select-Object -First 1).NumberOfCores")
    for prefix in ["Intel(R) Core(TM) ", "Intel(R) ", "AMD "]:
        name = name.replace(prefix, "")
    value = f"{name.strip()}  {cores}c" if cores else name.strip()
    STATIC_INFO["cpu_name"] = value
    return value


def get_gpu_name():
    if "gpu_name" in STATIC_INFO:
        return STATIC_INFO["gpu_name"]
    name = ps("(Get-CimInstance Win32_VideoController | Select-Object -First 1).Name")
    for prefix in ["NVIDIA ", "AMD ", "Intel(R) "]:
        name = name.replace(prefix, "")
    value = name.strip()
    STATIC_INFO["gpu_name"] = value
    return value


def get_memory_total_text():
    if "memory_total" not in STATIC_INFO:
        STATIC_INFO["memory_total"] = fmt_storage(psutil.virtual_memory().total / (1024 ** 3))
    return STATIC_INFO["memory_total"]


def get_storage_total_text():
    if "storage_total" not in STATIC_INFO:
        STATIC_INFO["storage_total"] = fmt_storage(psutil.disk_usage("C:/").total / (1024 ** 3))
    return STATIC_INFO["storage_total"]


def get_uptime():
    delta = int(time.time() - psutil.boot_time())
    days = delta // 86400
    hours = (delta % 86400) // 3600
    minutes = (delta % 3600) // 60
    return f"{days}d {hours}h {minutes}m"


def fmt_storage(gb):
    if gb >= 1000:
        return f"{gb / 1024:.1f} TB"
    return f"{gb:.0f} GB"


def fmt_bytes(b):
    for unit in ["B", "KB", "MB", "GB"]:
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


# ── weather ─────────────────────────────────────────────
def get_weather():
    now = time.time()
    if WEATHER_CACHE["data"] and now - WEATHER_CACHE["time"] < 300:
        return WEATHER_CACHE["data"]
    try:
        loc = json.loads(
            urllib.request.urlopen("https://ipapi.co/json/", timeout=6).read().decode("utf-8")
        )
        lat = loc.get("latitude")
        lon = loc.get("longitude")
        if lat is None or lon is None:
            return None
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,weather_code"
            "&temperature_unit=fahrenheit"
        )
        data = json.loads(urllib.request.urlopen(url, timeout=8).read().decode("utf-8"))
        current = data.get("current", {})
        code = int(current.get("weather_code", 3))
        weather = {
            "temp_f": round(float(current.get("temperature_2m", 0))),
            "desc": weather_code_to_desc(code),
            "code": code,
        }
        WEATHER_CACHE["data"] = weather
        WEATHER_CACHE["time"] = now
        return weather
    except Exception:
        return None


def weather_code_to_desc(code):
    mapping = {
        0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "cloudy",
        45: "fog", 48: "rime fog", 51: "light drizzle", 53: "drizzle",
        55: "dense drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
        71: "light snow", 73: "snow", 75: "heavy snow", 80: "rain showers",
        81: "heavy showers", 82: "violent showers", 95: "thunderstorm",
    }
    return mapping.get(code, "conditions")


def weather_ascii(code):
    if code in (0, 1):
        return ["    \\  |  /    ", "      .-.      ", "   -- ( ) --   ", "      '-'      ", "    /  |  \\    "]
    if code in (2, 3):
        return ["                ", "      .--.      ", "   .-(    ).    ", "  (___.__)__)   ", "                "]
    if code in (45, 48):
        return ["                ", "   -  -  -  -   ", "    -  -  -     ", "   -  -  -  -   ", "                "]
    if code in (51, 53, 55, 61, 63, 65, 80, 81, 82):
        return ["      .--.      ", "   .-(    ).    ", "  (___.__)__)   ", "   / / / / /    ", "  / / / / /     "]
    if code in (71, 73, 75):
        return ["      .--.      ", "   .-(    ).    ", "  (___.__)__)   ", "    *  *  *     ", "   *  *  *      "]
    if code == 95:
        return ["      .--.      ", "   .-(    ).    ", "  (___.__)__)   ", "     / /        ", "    /_/         "]
    return ["      .--.      ", "   .-(    ).    ", "  (___.__)__)   "]


# ── font loader ─────────────────────────────────────────
def load_font(size, bold=False):
    fonts_dir = "C:/Windows/Fonts"
    chosen = FONT_BOLD if bold else FONT_NAME
    try:
        return ImageFont.truetype(f"{fonts_dir}/{chosen}", size)
    except OSError:
        return ImageFont.truetype(f"{fonts_dir}/{FALLBACK_FONT}", size)


# ── drawing helpers ─────────────────────────────────────
def draw_bg(draw, width, height):
    for y in range(0, height, 28):
        for x in range(0, width, 28):
            draw.point((x, y), fill=GRID)


def draw_frame(draw, x, y, w, h, title, font):
    draw.rectangle((x, y, x + w, y + h), outline=DIM)
    title_text = f" {title} "
    tw = draw.textlength(title_text, font=font)
    draw.rectangle((x + 18, y - 12, x + 18 + tw, y + 12), fill=BG)
    draw.text((x + 18, y - 10), title_text, font=font, fill=WHITE)


def draw_bar(draw, x, y, width, pct, height=14):
    draw.rectangle((x, y, x + width, y + height), fill=BAR_BG, outline=DIM)
    inner = max(0, int((width - 4) * min(max(pct, 0), 100) / 100))
    if inner > 0:
        draw.rectangle((x + 2, y + 2, x + 2 + inner, y + height - 2), fill=MID)


def draw_sparkline(draw, x, y, values, width, height):
    if len(values) < 2:
        return
    maximum = max(max(values), 1)
    bar_w = max(2, width // len(values))
    for i, value in enumerate(values):
        bar_h = max(1, int((value / maximum) * height))
        bx = x + i * bar_w
        draw.rectangle((bx, y + height - bar_h, bx + bar_w - 2, y + height), fill=ACCENT)


# ── state & metrics ─────────────────────────────────────
def update_net_rates():
    counters = psutil.net_io_counters()
    now = time.time()
    if NET_STATE["time"] is None:
        NET_STATE["sent"] = counters.bytes_sent
        NET_STATE["recv"] = counters.bytes_recv
        NET_STATE["time"] = now
        return counters.bytes_sent, counters.bytes_recv
    NET_STATE["sent"] = counters.bytes_sent
    NET_STATE["recv"] = counters.bytes_recv
    NET_STATE["time"] = now
    return counters.bytes_sent, counters.bytes_recv


def update_process_state():
    current = {}
    for proc in psutil.process_iter(["pid", "name", "cpu_times", "memory_percent"]):
        try:
            info = proc.info
            cpu_times = info.get("cpu_times")
            if not cpu_times:
                continue
            total_cpu = float(cpu_times.user + cpu_times.system)
            current[info["pid"]] = {
                "name": info.get("name") or "?",
                "cpu_total": total_cpu,
                "mem": info.get("memory_percent") or 0.0,
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    now = time.time()
    if not PROC_STATE:
        PROC_STATE["time"] = now
        PROC_STATE["items"] = current
        return []
    dt = max(now - PROC_STATE["time"], 0.1)
    cpu_count = max(psutil.cpu_count() or 1, 1)
    rows = []
    for pid, item in current.items():
        prev = PROC_STATE["items"].get(pid)
        if not prev:
            continue
        delta = item["cpu_total"] - prev["cpu_total"]
        cpu_pct = max(0.0, min(999.0, (delta / dt) * 100 / cpu_count))
        name = item["name"]
        if name.lower() in ("idle", "system idle process", "python.exe", "pythonw.exe"):
            continue
        rows.append((name, cpu_pct, item["mem"]))
    PROC_STATE["time"] = now
    PROC_STATE["items"] = current
    rows.sort(key=lambda row: row[1], reverse=True)
    return rows[:4]


def overlay_suppression_loop():
    while True:
        try:
            hide_desktop_overlay()
        except Exception:
            pass
        time.sleep(0.25)


def apply_wallpaper(path: Path):
    SPI_SETDESKWALLPAPER = 0x0014
    SPIF_UPDATEINIFILE = 0x01
    SPIF_SENDCHANGE = 0x02
    ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETDESKWALLPAPER,
        0,
        str(path),
        SPIF_UPDATEINIFILE | SPIF_SENDCHANGE,
    )


def hide_desktop_overlay():
    user32 = ctypes.windll.user32
    progman = user32.FindWindowW("Progman", None)
    if not progman:
        return False

    overlay_hwnds = []

    def callback(hwnd, _lparam):
        class_name = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_name, 256)
        if "DesktopOverlay" in class_name.value:
            overlay_hwnds.append(hwnd)
        return True

    user32.EnumChildWindows(progman, EnumWindowsProc(callback), 0)
    hidden_any = False
    for hwnd in overlay_hwnds:
        try:
            user32.ShowWindow(hwnd, 0)
            user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0080)
            hidden_any = True
        except Exception:
            pass
    return hidden_any


def try_set_lock_screen(path: Path):
    ps_script = (
        "Add-Type -AssemblyName System.Runtime.WindowsRuntime; "
        "$f=[Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime]::GetFileFromPathAsync('"
        + str(path).replace("\\", "\\\\")
        + "').GetAwaiter().GetResult(); "
        "[Windows.System.UserProfile.LockScreen,Windows.System.UserProfile,ContentType=WindowsRuntime]::SetImageFileAsync($f).GetAwaiter().GetResult()"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=20,
            creationflags=NO_WINDOW,
        )
        return result.returncode == 0
    except Exception:
        return False


def write_startup_launcher(project_dir: Path):
    startup_dir = Path(os.path.expanduser(r"~\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup"))
    startup_dir.mkdir(parents=True, exist_ok=True)
    vbs_path = startup_dir / "monochrome-wallpaper.vbs"
    py_path = project_dir / "generate_wallpaper.py"
    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    if not Path(pythonw).exists():
        pythonw = sys.executable
    launcher = (
        'Set WshShell = CreateObject("WScript.Shell")\r\n'
        f'WshShell.Run "\"{pythonw}\" \"{py_path}\"", 0, False\r\n'
    )
    vbs_path.write_text(launcher, encoding="ascii")
    return vbs_path


# ── render ──────────────────────────────────────────────
def generate_wallpaper_image(output_path: Path, width: int, height: int, compact=False):
    global CPU_HISTORY
    now = datetime.now()
    img = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img)
    draw_bg(draw, width, height)

    f14 = load_font(14)
    f16 = load_font(16)
    f18 = load_font(18)
    f34 = load_font(34, bold=True)

    # Calculate layout matching
    margin_x = int(width * 0.1)
    margin_top = 260 if not compact else 180
    col_gap = 100
    col_w = (width - margin_x * 2 - col_gap) // 2
    lx = margin_x
    rx = margin_x + col_w + col_gap

    # Get metrics ONLY ONCE PER INTERVAL
    cpu_pct = psutil.cpu_percent(interval=0) # 0 interval so it doesn't block the loop
    if len(CPU_HISTORY) == 0 or cpu_pct > 0: # Ensure valid history
        CPU_HISTORY.append(cpu_pct)
    if len(CPU_HISTORY) > 60:
        CPU_HISTORY.pop(0)

    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("C:/")
    sent_total, recv_total = update_net_rates()
    procs = update_process_state()
    weather = get_weather()

    # ════════════════════════════════════════════════════
    # LEFT COLUMN (HARDWARE)
    # ════════════════════════════════════════════════════
    # SYSTEM & CPU
    ly = margin_top
    draw_frame(draw, lx, ly, col_w, 205, "SYSTEM & CPU", f16)
    iy = ly + 35
    draw.text((lx + 24, iy), get_cpu_name(), font=f18, fill=WHITE)
    draw.text((lx + col_w - 70, iy), f"{cpu_pct:3.0f}%", font=f18, fill=WHITE)
    iy += 34
    draw_bar(draw, lx + 24, iy, col_w - 48, cpu_pct)
    iy += 26
    draw_sparkline(draw, lx + 24, iy, CPU_HISTORY, col_w - 48, 42)
    iy += 60
    draw.text((lx + 24, iy), "gpu:", font=f14, fill=DIM)
    draw.text((lx + 74, iy), get_gpu_name(), font=f14, fill=MID)
    iy += 22
    draw.text((lx + 24, iy), "uptime:", font=f14, fill=DIM)
    draw.text((lx + 92, iy), get_uptime(), font=f14, fill=MID)

    # MEMORY
    ly += 235 # Ensure vertical gap matches right side
    draw_frame(draw, lx, ly, col_w, 125, "MEMORY", f16)
    iy = ly + 35
    used_gb = ram.used / (1024 ** 3)
    draw.text((lx + 24, iy), f"{fmt_storage(used_gb)} / {get_memory_total_text()}", font=f18, fill=WHITE)
    draw.text((lx + col_w - 70, iy), f"{ram.percent:3.0f}%", font=f18, fill=WHITE)
    iy += 34
    draw_bar(draw, lx + 24, iy, col_w - 48, ram.percent)

    # STORAGE
    ly += 155
    draw_frame(draw, lx, ly, col_w, 125, "STORAGE", f16)
    iy = ly + 35
    used_disk_gb = (disk.total - disk.free) / (1024 ** 3)
    draw.text((lx + 24, iy), f"C:\\   {fmt_storage(used_disk_gb)} / {get_storage_total_text()}", font=f18, fill=WHITE)
    draw.text((lx + col_w - 70, iy), f"{disk.percent:3.0f}%", font=f18, fill=WHITE)
    iy += 34
    draw_bar(draw, lx + 24, iy, col_w - 48, disk.percent)

    # ════════════════════════════════════════════════════
    # RIGHT COLUMN (WEATHER & NETWORK & PROCESSES)
    # ════════════════════════════════════════════════════
    ry = margin_top

    # WEATHER
    draw_frame(draw, rx, ry, col_w, 165, "WEATHER", f16)
    if weather:
        art_y = ry + 32
        for line in weather_ascii(weather["code"]):
            draw.text((rx + 26, art_y), line, font=f18, fill=MID)
            art_y += 22
        draw.text((rx + 230, ry + 42), f"{weather['temp_f']}F", font=f34, fill=WHITE)
        draw.text((rx + 232, ry + 92), weather["desc"], font=f18, fill=BRIGHT)
    else:
        draw.text((rx + 26, ry + 48), "weather unavailable", font=f18, fill=DIM)

    # NETWORK
    ry += 195
    draw_frame(draw, rx, ry, col_w, 100, "NETWORK", f16)
    iy = ry + 35
    draw.text((rx + 24, iy), "up:", font=f16, fill=DIM)
    draw.text((rx + 70, iy), fmt_bytes(sent_total), font=f18, fill=WHITE)
    draw.text((rx + col_w // 2, iy), "down:", font=f16, fill=DIM)
    draw.text((rx + col_w // 2 + 70, iy), fmt_bytes(recv_total), font=f18, fill=WHITE)

    # TOP PROCESSES
    ry += 130
    draw_frame(draw, rx, ry, col_w, 165, "TOP PROCESSES", f16)
    iy = ry + 34
    header = f"{'NAME':<22} {'CPU':>6}  {'MEM':>6}"
    draw.text((rx + 24, iy), header, font=f14, fill=DIM)
    iy += 24
    if not procs:
        draw.text((rx + 24, iy), "sampling...", font=f14, fill=DIM)
    for name, cpu, mem in procs:
        line = f"{name[:20]:<22} {cpu:5.1f}%  {mem:5.1f}%"
        draw.text((rx + 24, iy), line, font=f14, fill=BRIGHT if cpu > 2 else MID)
        iy += 24

    # ════════════════════════════════════════════════════
    # BOTTOM
    # ════════════════════════════════════════════════════
    stamp = f"updated {now.strftime('%H:%M:%S')}  |  interval {INTERVAL}s"
    tw = draw.textlength(stamp, font=f14)
    draw.text(((width - tw) / 2, height - TASKBAR_CLEARANCE), stamp, font=f14, fill=DIM)

    img.save(output_path)
    return output_path


def generate_assets(project_dir: Path):
    wall_path = project_dir / "wallpaper.bmp"
    lock_path = project_dir / "lockscreen.bmp"
    width, height = get_screen_size()
    generate_wallpaper_image(wall_path, width, height, compact=False)
    generate_wallpaper_image(lock_path, width, height, compact=True)
    return wall_path, lock_path


def install_runtime(project_dir: Path):
    write_startup_launcher(project_dir)


def main():
    project_dir = Path(__file__).parent
    print(f"monochrome-wallpaper | refreshing every {INTERVAL}s")
    install_runtime(project_dir)
    threading.Thread(target=overlay_suppression_loop, daemon=True).start()

    lockscreen_applied = False
    while True:
        try:
            wall_path, lock_path = generate_assets(project_dir)
            hide_desktop_overlay()
            apply_wallpaper(wall_path)
            hide_desktop_overlay()
            if not lockscreen_applied:
                lockscreen_applied = try_set_lock_screen(lock_path)
        except Exception:
            pass
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
