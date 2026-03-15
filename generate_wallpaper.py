"""
monochrome-wallpaper
Live-updating monochrome system dashboard wallpaper for Windows.
Auto-detects hardware, weather, and usage. No personal data rendered.
"""

import ctypes
import ctypes.wintypes
import json
import os
import platform
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
TASKBAR_H = 100
FONTS_DIR = "C:/Windows/Fonts"
FONT_REGULAR = "CascadiaMono.ttf"
FONT_BOLD = "CascadiaMonoNF-Bold.otf"
FONT_FALLBACK = "consola.ttf"

BG = (16, 16, 16)
SUBTLE = (24, 24, 24)
DIM = (75, 75, 75)
MID = (140, 140, 140)
BRIGHT = (210, 210, 210)
WHITE = (240, 240, 240)
BAR_BG = (28, 28, 28)
BAR_FILL = (100, 100, 100)
GRAPH_BAR = (90, 90, 90)

# ── runtime state ───────────────────────────────────────
_cpu_hist = []
_net_hist = []
_net_prev = {"s": 0, "r": 0, "t": 0}
_proc_prev = {"t": 0, "items": {}}
_weather_cache = {"d": None, "t": 0}
_static = {}
_snap = {}
NO_WIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_EnumCB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)


# ── helpers ─────────────────────────────────────────────
def _ps(cmd):
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=10,
            creationflags=NO_WIN,
        )
        return r.stdout.strip()
    except Exception:
        return ""


def _font(sz, bold=False):
    name = FONT_BOLD if bold else FONT_REGULAR
    try:
        return ImageFont.truetype(f"{FONTS_DIR}/{name}", sz)
    except OSError:
        try:
            return ImageFont.truetype(f"{FONTS_DIR}/{FONT_FALLBACK}", sz)
        except OSError:
            return ImageFont.load_default()


def _fmt_stor(gb):
    return f"{gb / 1024:.1f} TB" if gb >= 1000 else f"{gb:.0f} GB"


def _fmt_bytes(b):
    for u in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} TB"


def _screen():
    try:
        u = ctypes.windll.user32
        u.SetProcessDPIAware()
        return u.GetSystemMetrics(0), u.GetSystemMetrics(1)
    except Exception:
        return 1920, 1080


# ── static info (queried once) ──────────────────────────
def _cpu_name():
    if "cpu" in _static:
        return _static["cpu"]
    n = _ps("(Get-CimInstance Win32_Processor | Select-Object -First 1).Name")
    c = _ps("(Get-CimInstance Win32_Processor | Select-Object -First 1).NumberOfCores")
    for p in ("Intel(R) Core(TM) ", "Intel(R) ", "AMD "):
        n = n.replace(p, "")
    v = f"{n.strip()}  {c}c" if c else n.strip()
    _static["cpu"] = v
    return v


def _gpu_name():
    if "gpu" in _static:
        return _static["gpu"]
    n = _ps("(Get-CimInstance Win32_VideoController | Select-Object -First 1).Name")
    for p in ("NVIDIA ", "AMD ", "Intel(R) "):
        n = n.replace(p, "")
    v = n.strip()
    _static["gpu"] = v
    return v


def _os_name():
    if "os" in _static:
        return _static["os"]
    v = f"{platform.system()} {platform.release()}"
    _static["os"] = v
    return v


def _ram_total():
    if "ramt" not in _static:
        _static["ramt"] = _fmt_stor(psutil.virtual_memory().total / (1024**3))
    return _static["ramt"]


def _disk_total():
    if "diskt" not in _static:
        _static["diskt"] = _fmt_stor(psutil.disk_usage("C:/").total / (1024**3))
    return _static["diskt"]


# ── live metrics ────────────────────────────────────────
def _uptime():
    d = int(time.time() - psutil.boot_time())
    return f"{d // 86400}d {(d % 86400) // 3600}h {(d % 3600) // 60}m"


def _net():
    c = psutil.net_io_counters()
    _net_prev["s"] = c.bytes_sent
    _net_prev["r"] = c.bytes_recv
    _net_prev["t"] = time.time()
    return c.bytes_sent, c.bytes_recv


def _procs():
    cur = {}
    for p in psutil.process_iter(["pid", "name", "cpu_times", "memory_percent"]):
        try:
            i = p.info
            ct = i.get("cpu_times")
            if not ct:
                continue
            cur[i["pid"]] = {
                "n": i.get("name") or "?",
                "c": float(ct.user + ct.system),
                "m": i.get("memory_percent") or 0.0,
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    now = time.time()
    if not _proc_prev["items"]:
        _proc_prev.update(t=now, items=cur)
        return []
    dt = max(now - _proc_prev["t"], 0.1)
    nc = max(psutil.cpu_count() or 1, 1)
    rows = []
    skip = {"idle", "system idle process", "python.exe", "pythonw.exe",
            "python3.13.exe", "pythonw3.13.exe"}
    for pid, it in cur.items():
        prev = _proc_prev["items"].get(pid)
        if not prev:
            continue
        cp = max(0, min(999, (it["c"] - prev["c"]) / dt * 100 / nc))
        if it["n"].lower() not in skip:
            rows.append((it["n"], cp, it["m"]))
    _proc_prev.update(t=now, items=cur)
    rows.sort(key=lambda r: r[1], reverse=True)
    return rows[:5]


# ── weather ─────────────────────────────────────────────
WMO_DESC = {
    0: "clear sky", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "rime fog",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    56: "freezing drizzle", 57: "heavy freezing drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain",
    66: "freezing rain", 67: "heavy freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow",
    77: "snow grains",
    80: "light showers", 81: "showers", 82: "heavy showers",
    85: "light snow showers", 86: "heavy snow showers",
    95: "thunderstorm", 96: "thunderstorm + hail", 99: "severe thunderstorm",
}

WMO_ART = {
    "clear": [
        r"        \   |   /        ",
        r"         \  |  /         ",
        r"     ---  (   )  ---     ",
        r"         /  |  \         ",
        r"        /   |   \        ",
    ],
    "partly": [
        r"    \  |  /              ",
        r"     (   )  .---.       ",
        r"    / |  .-(     ).     ",
        r"       (___.___.__)     ",
        r"                        ",
    ],
    "cloudy": [
        r"                        ",
        r"         .---.          ",
        r"      .-(     ).        ",
        r"     (___.___.__)       ",
        r"                        ",
    ],
    "fog": [
        r"                        ",
        r"     ---  ---  ---      ",
        r"      ---  ---  ---     ",
        r"     ---  ---  ---      ",
        r"                        ",
    ],
    "drizzle": [
        r"         .---.          ",
        r"      .-(     ).        ",
        r"     (___.___.__)       ",
        r"       .  .  .  .       ",
        r"      .  .  .  .        ",
    ],
    "rain": [
        r"         .---.          ",
        r"      .-(     ).        ",
        r"     (___.___.__)       ",
        r"      /  /  /  /        ",
        r"     /  /  /  /         ",
    ],
    "heavy_rain": [
        r"         .---.          ",
        r"      .-(     ).        ",
        r"     (___.___.__)       ",
        r"     // // // //        ",
        r"    // // // //         ",
    ],
    "snow": [
        r"         .---.          ",
        r"      .-(     ).        ",
        r"     (___.___.__)       ",
        r"      *  *  *  *        ",
        r"     *  *  *  *         ",
    ],
    "thunder": [
        r"         .---.          ",
        r"      .-(     ).        ",
        r"     (___.___.__)       ",
        r"       /_/   /_/        ",
        r"      /     /           ",
    ],
    "hail": [
        r"         .---.          ",
        r"      .-(     ).        ",
        r"     (___.___.__)       ",
        r"      o  o  o  o        ",
        r"     o  o  o  o         ",
    ],
}


def _wmo_art(code):
    if code in (0, 1):
        return WMO_ART["clear"]
    if code == 2:
        return WMO_ART["partly"]
    if code == 3:
        return WMO_ART["cloudy"]
    if code in (45, 48):
        return WMO_ART["fog"]
    if code in (51, 53, 55, 56, 57):
        return WMO_ART["drizzle"]
    if code in (61, 63, 80, 81):
        return WMO_ART["rain"]
    if code in (65, 66, 67, 82):
        return WMO_ART["heavy_rain"]
    if code in (71, 73, 75, 77, 85, 86):
        return WMO_ART["snow"]
    if code in (95, 96, 99):
        return WMO_ART["thunder"]
    return WMO_ART["cloudy"]


def _weather():
    now = time.time()
    if _weather_cache["d"] and now - _weather_cache["t"] < 300:
        return _weather_cache["d"]
    try:
        loc = json.loads(urllib.request.urlopen(
            "https://ipapi.co/json/", timeout=6
        ).read().decode())
        lat, lon = loc.get("latitude"), loc.get("longitude")
        if lat is None:
            return None
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,weather_code"
            f"&temperature_unit=fahrenheit"
        )
        data = json.loads(urllib.request.urlopen(url, timeout=8).read().decode())
        cur = data.get("current", {})
        code = int(cur.get("weather_code", 3))
        w = {
            "temp": round(float(cur.get("temperature_2m", 0))),
            "desc": WMO_DESC.get(code, "conditions"),
            "code": code,
        }
        _weather_cache.update(d=w, t=now)
        return w
    except Exception:
        return None


# ── snapshot (collect once, render twice) ───────────────
def _collect():
    cpu = psutil.cpu_percent(interval=0)
    _cpu_hist.append(cpu)
    if len(_cpu_hist) > 60:
        _cpu_hist.pop(0)

    sent, recv = _net()
    _net_hist.append(sent + recv)
    if len(_net_hist) > 60:
        _net_hist.pop(0)

    _snap.update(
        cpu=cpu,
        cpu_h=list(_cpu_hist),
        ram=psutil.virtual_memory(),
        disk=psutil.disk_usage("C:/"),
        sent=sent, recv=recv,
        net_d=[max(0, _net_hist[i] - _net_hist[i-1]) for i in range(1, len(_net_hist))],
        procs=_procs(),
        weather=_weather(),
        now=datetime.now(),
    )


# ── drawing primitives ─────────────────────────────────
def _draw_bg(d, w, h):
    for y in range(0, h, 32):
        for x in range(0, w, 32):
            d.point((x, y), fill=SUBTLE)


def _frame(d, x, y, w, h, title, f):
    d.rectangle((x, y, x + w, y + h), outline=DIM)
    t = f" {title} "
    tw = d.textlength(t, font=f)
    d.rectangle((x + 16, y - 11, x + 18 + tw, y + 11), fill=BG)
    d.text((x + 17, y - 9), t, font=f, fill=WHITE)


def _bar(d, x, y, w, pct, h=14):
    d.rectangle((x, y, x + w, y + h), fill=BAR_BG, outline=DIM)
    fill = max(0, int((w - 4) * min(max(pct, 0), 100) / 100))
    if fill > 0:
        d.rectangle((x + 2, y + 2, x + 2 + fill, y + h - 2), fill=BAR_FILL)


def _spark(d, x, y, vals, w, h):
    if len(vals) < 2:
        return
    mx = max(max(vals), 1)
    bw = max(2, w // len(vals))
    for i, v in enumerate(vals):
        bh = max(1, int((v / mx) * h))
        bx = x + i * bw
        d.rectangle((bx, y + h - bh, bx + bw - 2, y + h), fill=GRAPH_BAR)


def _graph_bg(d, x, y, w, h):
    d.rectangle((x, y, x + w, y + h), fill=BAR_BG)


# ── render ──────────────────────────────────────────────
def _render(out, W, H, compact=False):
    now = _snap.get("now", datetime.now())
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    _draw_bg(d, W, H)

    f12 = _font(12)
    f14 = _font(14)
    f16 = _font(16)
    f18 = _font(18)
    f32 = _font(32, bold=True)

    mx = int(W * 0.1)
    top = 240 if not compact else 160
    gap = 80
    cw = (W - mx * 2 - gap) // 2
    lx, rx = mx, mx + cw + gap
    pad = 24
    inner = cw - pad * 2

    cpu = _snap.get("cpu", 0)
    cpu_h = _snap.get("cpu_h", [])
    ram = _snap.get("ram", psutil.virtual_memory())
    disk = _snap.get("disk", psutil.disk_usage("C:/"))
    sent = _snap.get("sent", 0)
    recv = _snap.get("recv", 0)
    net_d = _snap.get("net_d", [])
    procs = _snap.get("procs", [])
    weather = _snap.get("weather")

    # ── LEFT: System & CPU ──────────────────────────────
    ly = top
    _frame(d, lx, ly, cw, 210, "SYSTEM", f16)
    iy = ly + 32
    d.text((lx + pad, iy), _cpu_name(), font=f18, fill=WHITE)
    d.text((lx + cw - 68, iy), f"{cpu:.0f}%", font=f18, fill=WHITE)
    iy += 32
    _bar(d, lx + pad, iy, inner, cpu)
    iy += 24
    _graph_bg(d, lx + pad, iy, inner, 46)
    _spark(d, lx + pad, iy, cpu_h, inner, 46)
    iy += 62
    d.text((lx + pad, iy), f"gpu:  {_gpu_name()}", font=f14, fill=MID)
    iy += 20
    d.text((lx + pad, iy), f"up:   {_uptime()}    os:  {_os_name()}", font=f14, fill=MID)

    # ── LEFT: Memory ────────────────────────────────────
    ly += 240
    _frame(d, lx, ly, cw, 105, "MEMORY", f16)
    iy = ly + 32
    ug = ram.used / (1024**3)
    d.text((lx + pad, iy), f"{_fmt_stor(ug)} / {_ram_total()}", font=f18, fill=WHITE)
    d.text((lx + cw - 68, iy), f"{ram.percent:.0f}%", font=f18, fill=WHITE)
    iy += 32
    _bar(d, lx + pad, iy, inner, ram.percent)

    # ── LEFT: Storage ───────────────────────────────────
    ly += 135
    _frame(d, lx, ly, cw, 105, "STORAGE", f16)
    iy = ly + 32
    ug = (disk.total - disk.free) / (1024**3)
    d.text((lx + pad, iy), f"C:\\  {_fmt_stor(ug)} / {_disk_total()}", font=f18, fill=WHITE)
    d.text((lx + cw - 68, iy), f"{disk.percent:.0f}%", font=f18, fill=WHITE)
    iy += 32
    _bar(d, lx + pad, iy, inner, disk.percent)

    # ── RIGHT: Weather ──────────────────────────────────
    ry = top
    _frame(d, rx, ry, cw, 170, "WEATHER", f16)
    if weather:
        ay = ry + 30
        for line in _wmo_art(weather["code"]):
            d.text((rx + pad, ay), line, font=f16, fill=MID)
            ay += 22
        d.text((rx + 230, ry + 40), f"{weather['temp']}F", font=f32, fill=WHITE)
        d.text((rx + 232, ry + 88), weather["desc"], font=f16, fill=BRIGHT)
    else:
        d.text((rx + pad, ry + 60), "no data", font=f16, fill=DIM)

    # ── RIGHT: Network ──────────────────────────────────
    ry += 200
    _frame(d, rx, ry, cw, 130, "NETWORK", f16)
    iy = ry + 32
    d.text((rx + pad, iy), "up:", font=f14, fill=DIM)
    d.text((rx + pad + 40, iy), _fmt_bytes(sent), font=f18, fill=WHITE)
    d.text((rx + cw // 2, iy), "down:", font=f14, fill=DIM)
    d.text((rx + cw // 2 + 60, iy), _fmt_bytes(recv), font=f18, fill=WHITE)
    iy += 40
    _graph_bg(d, rx + pad, iy, inner, 40)
    _spark(d, rx + pad, iy, net_d, inner, 40)

    # ── RIGHT: Processes ────────────────────────────────
    ry += 160
    _frame(d, rx, ry, cw, 150, "PROCESSES", f16)
    iy = ry + 32
    d.text((rx + pad, iy), f"{'NAME':<22}{'CPU':>7} {'MEM':>7}", font=f12, fill=DIM)
    iy += 22
    if not procs:
        d.text((rx + pad, iy), "sampling...", font=f12, fill=DIM)
    for name, cp, mm in procs:
        c = BRIGHT if cp > 2 else MID
        d.text((rx + pad, iy), f"{name[:20]:<22}{cp:6.1f}% {mm:6.1f}%", font=f12, fill=c)
        iy += 20

    # ── DECORATIONS ─────────────────────────────────────
    ac = (34, 34, 34)

    # top-left: subtle corner bracket
    d.line((mx, 40, mx + 60, 40), fill=ac, width=1)
    d.line((mx, 40, mx, 100), fill=ac, width=1)

    # top-right: matching corner bracket
    d.line((W - mx - 60, 40, W - mx, 40), fill=ac, width=1)
    d.line((W - mx, 40, W - mx, 100), fill=ac, width=1)

    # bottom-left: corner bracket
    bot = H - TASKBAR_H - 20
    d.line((mx, bot - 60, mx, bot), fill=ac, width=1)
    d.line((mx, bot, mx + 60, bot), fill=ac, width=1)

    # bottom-right: corner bracket
    d.line((W - mx, bot - 60, W - mx, bot), fill=ac, width=1)
    d.line((W - mx - 60, bot, W - mx, bot), fill=ac, width=1)

    # thin horizontal rule above the bottom stamp
    rule_y = H - TASKBAR_H - 8
    for i in range(0, W - mx * 2, 6):
        d.point((mx + i, rule_y), fill=ac)

    # center dotted line between columns
    pipe_x = lx + cw + gap // 2
    for yp in range(top + 10, top + 510, 8):
        d.point((pipe_x, yp), fill=ac)

    # ── BOTTOM STAMP ────────────────────────────────────
    stamp = f"updated {now.strftime('%H:%M:%S')}  |  {INTERVAL}s"
    tw = d.textlength(stamp, font=f14)
    d.text(((W - tw) / 2, H - TASKBAR_H), stamp, font=f14, fill=DIM)

    img.save(out)


# ── wallpaper / lockscreen / startup ────────────────────
def _apply_wall(p):
    ctypes.windll.user32.SystemParametersInfoW(0x0014, 0, str(p), 0x03)


def _apply_lock(bmp):
    try:
        jpg = bmp.with_suffix(".jpg")
        Image.open(bmp).save(jpg, "JPEG", quality=95)
        ps1 = bmp.parent / "set_lockscreen.ps1"
        if ps1.exists():
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", str(ps1), str(jpg)],
                capture_output=True, timeout=20, creationflags=NO_WIN,
            )
    except Exception:
        pass


def _hide_overlay():
    try:
        u32 = ctypes.windll.user32
        pm = u32.FindWindowW("Progman", None)
        if not pm:
            return
        hwnds = []

        def cb(h, _):
            cn = ctypes.create_unicode_buffer(256)
            u32.GetClassNameW(h, cn, 256)
            if "DesktopOverlay" in cn.value:
                hwnds.append(h)
            return True

        u32.EnumChildWindows(pm, _EnumCB(cb), 0)
        for h in hwnds:
            u32.ShowWindow(h, 0)
            u32.SetWindowPos(h, 0, 0, 0, 0, 0, 0x83)
    except Exception:
        pass


def _overlay_loop():
    while True:
        _hide_overlay()
        time.sleep(0.25)


def _disable_fade():
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(k, "WallpaperTransitionMode", 0, winreg.REG_DWORD, 0)
        winreg.CloseKey(k)
    except Exception:
        pass


def _install_startup(proj):
    startup = Path.home() / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup"
    startup.mkdir(parents=True, exist_ok=True)
    vbs = startup / "monochrome-wallpaper.vbs"
    pw = sys.executable.replace("python.exe", "pythonw.exe")
    if not Path(pw).exists():
        pw = sys.executable
    script = proj / "generate_wallpaper.py"
    vbs.write_text(
        'Set WshShell = CreateObject("WScript.Shell")\r\n'
        f'WshShell.Run Chr(34) & "{pw}" & Chr(34) & " " & Chr(34) & "{script}" & Chr(34), 0, False\r\n',
        encoding="ascii",
    )


# ── main ────────────────────────────────────────────────
def main():
    proj = Path(__file__).parent
    wall = proj / "wallpaper.bmp"
    lock = proj / "lockscreen.bmp"
    log = proj / "wallpaper.log"

    def _log(m):
        try:
            with open(log, "a") as f:
                f.write(f"[{datetime.now():%H:%M:%S}] {m}\n")
        except Exception:
            pass

    _install_startup(proj)
    _disable_fade()
    threading.Thread(target=_overlay_loop, daemon=True).start()
    _log("started")

    W, H = _screen()
    while True:
        try:
            _collect()
            _render(wall, W, H, compact=False)
            _render(lock, W, H, compact=True)
            _hide_overlay()
            _apply_wall(wall)
            _apply_lock(lock)
            _hide_overlay()
            _log("ok")
        except Exception as e:
            _log(f"err: {e}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
