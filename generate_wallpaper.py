"""
monochrome-wallpaper
Live monochrome system-info wallpaper. Minimalist, large, clean.
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

BG     = (18, 18, 18)  # Slightly darker for a sleeker look
DIM    = (60, 60, 60)
MID    = (120, 120, 120)
BRIGHT = (200, 200, 200)
WHITE  = (240, 240, 240)
BAR_BG = (30, 30, 30)


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


def weather_symbol(code):
    sunny = [113]
    partly = [116]
    cloudy = [119, 122]
    rain = [176, 263, 266, 293, 296, 299, 302, 305, 308, 353, 356, 359]
    snow = [179, 227, 230, 323, 326, 329, 332, 335, 338, 368, 371]
    thunder = [200, 386, 389, 392, 395]
    fog = [143, 248, 260]

    # Clean Unicode symbols acting as monochrome emojis
    if code in sunny:     return "O" # Using O since some fonts lack the sun glyph
    elif code in partly:  return "o"
    elif code in cloudy:  return "C" # Cloud replacement
    elif code in rain:    return "/"
    elif code in snow:    return "*"
    elif code in thunder: return "~"
    elif code in fog:     return "-"
    return "C"


def weather_ascii(code):
    """Large typography-based weather icon."""
    sunny = [113]
    partly = [116]
    cloudy = [119, 122]
    rain = [176, 263, 266, 293, 296, 299, 302, 305, 308, 353, 356, 359]
    snow = [179, 227, 230, 323, 326, 329, 332, 335, 338, 368, 371]
    thunder = [200, 386, 389, 392, 395]
    fog = [143, 248, 260]

    if code in sunny:
        return [" \\ | / ", " - O - ", " / | \\ "]
    elif code in partly:
        return [" \\ |   ", " - O ~ ", " /   ~ "]
    elif code in cloudy:
        return ["  ~~~  ", " ~~~~~ ", "  ~~~  "]
    elif code in rain:
        return [" ~~~~~ ", " / / / ", "/ / /  "]
    elif code in snow:
        return [" ~~~~~ ", " * * * ", "* * *  "]
    elif code in thunder:
        return [" ~~~~~ ", "  / /  ", " /     "]
    elif code in fog:
        return [" - - - ", "  - -  ", " - - - "]
    return ["  ~~~  ", " ~~~~~ ", "  ~~~  "]


# ── font loader ─────────────────────────────────────────
def load_font(size, bold=False):
    fd = "C:/Windows/Fonts"
    name = FONT_BOLD if bold else FONT_NAME
    try:
        return ImageFont.truetype(f"{fd}/{name}", size)
    except OSError:
        return ImageFont.truetype(f"{fd}/{FALLBACK_FONT}", size)


# ── drawing helpers ─────────────────────────────────────
def draw_bar(d, x, y, width, pct, height=20):
    """Big, chunky, clean usage bar."""
    filled = int(width * min(pct, 100) / 100)
    d.rectangle((x, y, x + width, y + height), fill=BAR_BG)
    if filled > 0:
        d.rectangle((x, y, x + filled, y + height), fill=MID)


# ── main generate ───────────────────────────────────────
def generate(output_path: Path):
    W, H = get_screen_size()
    now = datetime.now()

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # ── Huge, readable fonts ──
    f16 = load_font(16)
    f20 = load_font(20)
    f24 = load_font(24)
    f32 = load_font(32, bold=True)
    f48 = load_font(48, bold=True)

    # Clean minimal background (no scanlines, just pure dark gray)

    margin_x = int(W * 0.1)
    margin_top = 300
    col_w = int(W * 0.35)

    # ==========================================
    # LEFT COLUMN (HARDWARE)
    # ==========================================
    lx = margin_x
    ly = margin_top

    # ── CPU ──
    d.text((lx, ly), "CPU", font=f24, fill=WHITE)
    ly += 35
    cpu_pct = psutil.cpu_percent(interval=0.5)
    d.text((lx, ly), get_cpu_name(), font=f20, fill=DIM)
    d.text((lx + col_w - 60, ly), f"{cpu_pct:.0f}%", font=f20, fill=WHITE)
    ly += 35
    draw_bar(d, lx, ly, col_w, cpu_pct)
    ly += 70

    # ── RAM ──
    d.text((lx, ly), "RAM", font=f24, fill=WHITE)
    ly += 35
    ram = psutil.virtual_memory()
    used_gb = ram.used / (1024**3)
    total_gb = ram.total / (1024**3)
    
    d.text((lx, ly), f"{fmt_storage(used_gb)} / {fmt_storage(total_gb)}", font=f20, fill=DIM)
    d.text((lx + col_w - 60, ly), f"{ram.percent:.0f}%", font=f20, fill=WHITE)
    ly += 35
    draw_bar(d, lx, ly, col_w, ram.percent)
    ly += 70

    # ── DISK ──
    d.text((lx, ly), "DISK", font=f24, fill=WHITE)
    ly += 35
    du = psutil.disk_usage("C:/")
    dk_free = du.free / (1024**3)
    dk_total = du.total / (1024**3)
    dk_used = dk_total - dk_free

    d.text((lx, ly), f"C:\  {fmt_storage(dk_used)} / {fmt_storage(dk_total)}", font=f20, fill=DIM)
    d.text((lx + col_w - 60, ly), f"{du.percent:.0f}%", font=f20, fill=WHITE)
    ly += 35
    draw_bar(d, lx, ly, col_w, du.percent)


    # ==========================================
    # RIGHT COLUMN (WEATHER & UPTIME)
    # ==========================================
    rx = W - margin_x - col_w
    ry = margin_top

    # ── WEATHER ──
    weather = get_weather()
    d.text((rx, ry), "WEATHER", font=f24, fill=WHITE)
    ry += 45

    if weather:
        # Draw nice ASCII icon
        art = weather_ascii(weather["code"])
        art_y = ry
        for line in art:
            d.text((rx, art_y), line, font=f24, fill=MID)
            art_y += 30
        
        # Draw Temp next to icon
        temp_str = f"{weather['temp_f']}°F"
        d.text((rx + 150, ry + 10), temp_str, font=f48, fill=WHITE)
        
        # Draw Desc
        ry = art_y + 20
        d.text((rx, ry), weather["desc"], font=f24, fill=DIM)
    else:
        d.text((rx, ry), "Unavailable", font=f20, fill=DIM)
    
    ry += 150

    # ── UPTIME ──
    d.text((rx, ry), "UPTIME", font=f24, fill=WHITE)
    ry += 40
    d.text((rx, ry), get_uptime(), font=f32, fill=DIM)

    # ==========================================
    # BOTTOM
    # ==========================================
    stamp = f"updated {now.strftime('%H:%M')}  |  interval {INTERVAL}s"
    tw = d.textlength(stamp, font=f16)
    d.text(((W - tw) / 2, H - 50), stamp, font=f16, fill=DIM)

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
