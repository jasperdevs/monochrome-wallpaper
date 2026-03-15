"""
monochrome-wallpaper
Live monochrome system-info wallpaper. 
Terminal aesthetic with box frames, sparklines, and pure data.
No personal data.
"""

import ctypes
import json
import os
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import psutil
from PIL import Image, ImageDraw, ImageFont


# ── config ──────────────────────────────────────────────
INTERVAL = 60
FONT_NAME = "CascadiaMono.ttf"
FONT_BOLD = "CascadiaMonoNF-Bold.otf"
FALLBACK_FONT = "consola.ttf"

BG     = (16, 16, 16)   # Deep dark background
GRID   = (30, 30, 30)   # Faint dot grid
DIM    = (70, 70, 70)   # Borders and subtle text
MID    = (130, 130, 130)
BRIGHT = (210, 210, 210)
WHITE  = (255, 255, 255)
BAR_BG = (28, 28, 28)
ACCENT = (100, 100, 100)


# ── screen ──────────────────────────────────────────────
def get_screen_size():
    try:
        u = ctypes.windll.user32
        u.SetProcessDPIAware()
        return u.GetSystemMetrics(0), u.GetSystemMetrics(1)
    except Exception:
        return 1920, 1080


def ps(cmd: str) -> str:
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=10,
        )
        return r.stdout.strip()
    except Exception:
        return ""


# ── system info ─────────────────────────────────────────
def get_cpu_name():
    name = ps("(Get-CimInstance Win32_Processor | Select-Object -First 1).Name")
    cores = ps("(Get-CimInstance Win32_Processor | Select-Object -First 1).NumberOfCores")
    for p in ["Intel(R) Core(TM) ", "Intel(R) ", "AMD "]:
        name = name.replace(p, "")
    return f"{name.strip()}  {cores}c" if cores else name.strip()


def get_uptime():
    delta = time.time() - psutil.boot_time()
    d = int(delta // 86400)
    h = int((delta % 86400) // 3600)
    m = int((delta % 3600) // 60)
    return f"{d}d {h}h {m}m"


def fmt_storage(gb):
    if gb >= 1000:
        return f"{gb/1024:.1f} TB"
    return f"{gb:.0f} GB"


def fmt_bytes(b):
    for unit in ["B", "KB", "MB", "GB"]:
        if b < 1024:
            return f"{b:.1f}{unit}"
        b /= 1024
    return f"{b:.1f}TB"


# ── weather (fresh every call) ──────────────────────────
def get_weather():
    try:
        req = urllib.request.Request(
            "https://wttr.in/?format=j1",
            headers={"User-Agent": "monochrome-wallpaper"},
        )
        r = urllib.request.urlopen(req, timeout=8)
        d = json.loads(r.read())
        cc = d["current_condition"][0]

        return {
            "temp_f": int(cc["temp_F"]),
            "temp_c": int(cc["temp_C"]),
            "desc": cc["weatherDesc"][0]["value"],
            "code": int(cc["weatherCode"]),
        }
    except Exception:
        return None


def weather_ascii(code):
    sunny = [113]
    partly = [116]
    cloudy = [119, 122]
    rain = [176, 263, 266, 293, 296, 299, 302, 305, 308, 353, 356, 359]
    snow = [179, 227, 230, 323, 326, 329, 332, 335, 338, 368, 371]
    thunder = [200, 386, 389, 392, 395]

    if code in sunny:
        return [
            "    \\  .  /    ",
            "  '-  O  -'  ",
            "    /  '  \\    "
        ]
    elif code in partly:
        return [
            "      .--.     ",
            "    -(    ).   ",
            "   (___.__)__) "
        ]
    elif code in cloudy:
        return [
            "      .--.     ",
            "   .-(    ).   ",
            "  (___.__)__)  "
        ]
    elif code in rain:
        return [
            "      .--.     ",
            "   .-(    ).   ",
            "  (___.__)__)  ",
            "   / / / /     "
        ]
    elif code in snow:
        return [
            "      .--.     ",
            "   .-(    ).   ",
            "  (___.__)__)  ",
            "   * * * *     "
        ]
    elif code in thunder:
        return [
            "      .--.     ",
            "   .-(    ).   ",
            "  (___.__)__)  ",
            "    /   /      "
        ]
    return [
        "      .--.     ",
        "   .-(    ).   ",
        "  (___.__)__)  "
    ]


# ── font loader ─────────────────────────────────────────
def load_font(size, bold=False):
    fd = "C:/Windows/Fonts"
    name = FONT_BOLD if bold else FONT_NAME
    try:
        return ImageFont.truetype(f"{fd}/{name}", size)
    except OSError:
        return ImageFont.truetype(f"{fd}/{FALLBACK_FONT}", size)


# ── drawing helpers ─────────────────────────────────────
def draw_bg(d, w, h):
    """Draw a subtle blueprint/dot grid pattern."""
    for y in range(0, h, 30):
        for x in range(0, w, 30):
            d.point((x, y), fill=GRID)


def draw_frame(d, x, y, w, h, title, font):
    """Draw a sleek terminal-style border frame with an overlapping title."""
    d.line((x, y, x+w, y), fill=DIM)         # top
    d.line((x, y+h, x+w, y+h), fill=DIM)     # bottom
    d.line((x, y, x, y+h), fill=DIM)         # left
    d.line((x+w, y, x+w, y+h), fill=DIM)     # right

    # Corners
    d.line((x, y, x+2, y), fill=MID)
    d.line((x, y, x, y+2), fill=MID)
    d.line((x+w-2, y, x+w, y), fill=MID)
    d.line((x+w, y, x+w, y+2), fill=MID)

    # Title plate
    title_str = f" {title} "
    tw = d.textlength(title_str, font=font)
    th = 14
    d.rectangle((x + 20, y - th, x + 20 + tw, y + th), fill=BG)
    d.text((x + 20, y - 10), title_str, font=font, fill=BRIGHT)


def draw_bar(d, x, y, width, pct, height=12):
    filled = int((width - 4) * min(pct, 100) / 100)
    d.rectangle((x, y, x + width, y + height), fill=BAR_BG, outline=DIM)
    if filled > 0:
        d.rectangle((x + 2, y + 2, x + 2 + filled, y + height - 2), fill=MID)


def draw_sparkline(d, x, y, values, width, height):
    if not values or len(values) < 2:
        return
    mx = max(max(values), 1)
    bw = max(2, width // len(values))
    for i, v in enumerate(values):
        bh = max(1, int((v / mx) * height))
        bx = x + i * bw
        d.rectangle((bx, y + height - bh, bx + bw - 2, y + height), fill=ACCENT)


# ── state ───────────────────────────────────────────────
CPU_HISTORY = []
NET_PREV = {"sent": 0, "recv": 0, "time": 0}


# ── main generate ───────────────────────────────────────
def generate(output_path: Path):
    global CPU_HISTORY, NET_PREV
    W, H = get_screen_size()
    now = datetime.now()

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    f14 = load_font(14)
    f16 = load_font(16)
    f18 = load_font(18)
    f24 = load_font(24, bold=True)
    f36 = load_font(36, bold=True)

    draw_bg(d, W, H)

    margin_x = int(W * 0.08)
    margin_top = 260
    col_gap = 60
    col_w = (W - (margin_x * 2) - col_gap) // 2

    lx = margin_x
    rx = margin_x + col_w + col_gap

    # ==========================================
    # LEFT COLUMN: HARDWARE
    # ==========================================
    ly = margin_top

    # ── SYSTEM & CPU ──
    frame_h = 190
    draw_frame(d, lx, ly, col_w, frame_h, "SYSTEM & CPU", f16)
    
    cpu_pct = psutil.cpu_percent(interval=0.5)
    CPU_HISTORY.append(cpu_pct)
    if len(CPU_HISTORY) > 60:
        CPU_HISTORY.pop(0)

    iy = ly + 35
    d.text((lx + 25, iy), get_cpu_name(), font=f18, fill=WHITE)
    d.text((lx + col_w - 90, iy), f"{cpu_pct:3.0f}%", font=f18, fill=WHITE)
    iy += 35
    draw_bar(d, lx + 25, iy, col_w - 50, cpu_pct)
    iy += 25
    draw_sparkline(d, lx + 25, iy, CPU_HISTORY, col_w - 50, 40)
    
    iy += 60
    d.text((lx + 25, iy), f"uptime:", font=f14, fill=DIM)
    d.text((lx + 100, iy), get_uptime(), font=f14, fill=MID)
    ly += frame_h + 40

    # ── MEMORY ──
    frame_h = 120
    draw_frame(d, lx, ly, col_w, frame_h, "MEMORY", f16)
    
    ram = psutil.virtual_memory()
    used_gb = ram.used / (1024**3)
    total_gb = ram.total / (1024**3)
    
    iy = ly + 35
    d.text((lx + 25, iy), f"{fmt_storage(used_gb)} / {fmt_storage(total_gb)}", font=f18, fill=WHITE)
    d.text((lx + col_w - 90, iy), f"{ram.percent:3.0f}%", font=f18, fill=WHITE)
    iy += 35
    draw_bar(d, lx + 25, iy, col_w - 50, ram.percent)
    ly += frame_h + 40

    # ── DISK ──
    frame_h = 120
    draw_frame(d, lx, ly, col_w, frame_h, "STORAGE", f16)
    
    du = psutil.disk_usage("C:/")
    dk_free = du.free / (1024**3)
    dk_total = du.total / (1024**3)
    dk_used = dk_total - dk_free

    iy = ly + 35
    d.text((lx + 25, iy), f"C:\\   {fmt_storage(dk_used)} / {fmt_storage(dk_total)}", font=f18, fill=WHITE)
    d.text((lx + col_w - 90, iy), f"{du.percent:3.0f}%", font=f18, fill=WHITE)
    iy += 35
    draw_bar(d, lx + 25, iy, col_w - 50, du.percent)


    # ==========================================
    # RIGHT COLUMN: NETWORK, PROCESSES, WEATHER
    # ==========================================
    ry = margin_top

    # ── WEATHER ──
    frame_h = 150
    draw_frame(d, rx, ry, col_w, frame_h, "WEATHER", f16)
    weather = get_weather()

    if weather:
        art = weather_ascii(weather["code"])
        art_y = ry + 35
        for line in art:
            d.text((rx + 30, art_y), line, font=f18, fill=MID)
            art_y += 24
        
        d.text((rx + 220, ry + 40), f"{weather['temp_f']}°F", font=f36, fill=WHITE)
        d.text((rx + 225, ry + 90), weather["desc"], font=f18, fill=BRIGHT)
    else:
        d.text((rx + 30, ry + 40), "Data unavailable", font=f16, fill=DIM)

    ry += frame_h + 40

    # ── NETWORK ──
    frame_h = 120
    draw_frame(d, rx, ry, col_w, frame_h, "NETWORK", f16)

    net = psutil.net_io_counters()
    now_t = time.time()
    if NET_PREV["time"] > 0:
        dt = max(now_t - NET_PREV["time"], 0.1)
        up_rate = (net.bytes_sent - NET_PREV["sent"]) / dt
        dn_rate = (net.bytes_recv - NET_PREV["recv"]) / dt
    else:
        up_rate = dn_rate = 0

    NET_PREV["sent"] = net.bytes_sent
    NET_PREV["recv"] = net.bytes_recv
    NET_PREV["time"] = now_t

    iy = ry + 35
    d.text((rx + 30, iy), "UP:", font=f16, fill=DIM)
    d.text((rx + 90, iy), f"{fmt_bytes(up_rate)}/s", font=f18, fill=WHITE)
    
    d.text((rx + col_w//2, iy), "DOWN:", font=f16, fill=DIM)
    d.text((rx + col_w//2 + 60, iy), f"{fmt_bytes(dn_rate)}/s", font=f18, fill=WHITE)
    iy += 45
    
    d.text((rx + 30, iy), f"Total Sent: {fmt_bytes(net.bytes_sent)}   |   Total Recv: {fmt_bytes(net.bytes_recv)}", font=f14, fill=DIM)

    ry += frame_h + 40

    # ── TOP PROCESSES ──
    frame_h = 180
    draw_frame(d, rx, ry, col_w, frame_h, "TOP PROCESSES", f16)
    
    # Get processes safely, exclude python itself from spiking it
    me = os.getpid()
    procs = []
    try:
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                info = p.info
                name = info.get("name", "")
                if info.get("pid") == me or name in ("System Idle Process", "Idle"):
                    continue
                cpu = info.get("cpu_percent", 0) or 0
                mem = info.get("memory_percent", 0) or 0
                procs.append((name, cpu, mem))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        procs.sort(key=lambda x: x[1], reverse=True)
    except Exception:
        pass

    iy = ry + 35
    d.text((rx + 30, iy), f"{'NAME':<25} {'CPU':>6}  {'MEM':>6}", font=f14, fill=DIM)
    iy += 25
    for name, cpu, mem in procs[:4]:
        short = name[:23]
        line = f"{short:<25} {cpu:5.1f}%  {mem:5.1f}%"
        d.text((rx + 30, iy), line, font=f14, fill=BRIGHT if cpu > 5 else MID)
        iy += 25

    # ==========================================
    # BOTTOM
    # ==========================================
    stamp = f"updated {now.strftime('%H:%M:%S')}  |  interval {INTERVAL}s"
    tw = d.textlength(stamp, font=f14)
    # Moved significantly up (H - 90) to ensure it clears the Windows Taskbar
    d.text(((W - tw) / 2, H - 90), stamp, font=f14, fill=DIM)

    img.save(output_path)
    return output_path


def apply_wallpaper(path: Path):
    SPI_SETDESKWALLPAPER = 0x0014
    SPIF_UPDATEINIFILE = 0x01
    SPIF_SENDCHANGE = 0x02
    ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETDESKWALLPAPER, 0, str(path),
        SPIF_UPDATEINIFILE | SPIF_SENDCHANGE,
    )


def main():
    output = Path(__file__).parent / "wallpaper.bmp"
    print(f"monochrome-wallpaper | refreshing every {INTERVAL}s")

    while True:
        try:
            generate(output)
            apply_wallpaper(output)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] updated")
        except Exception as e:
            print(f"[error] {e}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
