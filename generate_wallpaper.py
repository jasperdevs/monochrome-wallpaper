"""
monochrome-wallpaper
Live-updating monochrome system dashboard wallpaper for Windows.
Auto-detects hardware, weather, and usage. No personal data rendered.
"""

import ctypes
import ctypes.wintypes
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

from config_manager import load_config

# ── setup ───────────────────────────────────────────────
PROJ_DIR = Path(__file__).parent
FONTS_DIR = "C:/Windows/Fonts"
FONT_REGULAR = "CascadiaMono.ttf"
FONT_BOLD = "CascadiaMonoNF-Bold.otf"
FONT_FALLBACK = "consola.ttf"

# ── runtime state ───────────────────────────────────────
_cpu_hist = []
_net_hist = []
_net_prev = {"s": 0, "r": 0, "t": 0}
_proc_prev = {"t": 0, "items": {}}
_weather_cache = {"d": None, "t": 0}
_speedtest_cache = {"d": None, "t": 0, "running": False}
_static = {}
_snap = {}
NO_WIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


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


# ── static info ──────────────────────────
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
    now = time.time()
    if _net_prev["t"] == 0:
        _net_prev["s"] = c.bytes_sent
        _net_prev["r"] = c.bytes_recv
        _net_prev["t"] = now
        return 0.0, 0.0
    dt = max(now - _net_prev["t"], 0.1)
    up_rate = max(0.0, (c.bytes_sent - _net_prev["s"]) / dt)
    down_rate = max(0.0, (c.bytes_recv - _net_prev["r"]) / dt)
    _net_prev["s"] = c.bytes_sent
    _net_prev["r"] = c.bytes_recv
    _net_prev["t"] = now
    return up_rate, down_rate

def _run_speedtest_bg():
    global _speedtest_cache
    if _speedtest_cache["running"]:
        return
    _speedtest_cache["running"] = True
    
    def _do_test():
        try:
            import speedtest
            st = speedtest.Speedtest()
            st.get_best_server()
            d = st.download() / 1_000_000 # Convert to Mbps
            u = st.upload() / 1_000_000 # Convert to Mbps
            
            _speedtest_cache["d"] = {
                "down": d,
                "up": u,
                "ping": st.results.ping,
                "server": st.results.server.get('sponsor', 'Unknown')
            }
            _speedtest_cache["t"] = time.time()
        except Exception:
            pass
        finally:
            _speedtest_cache["running"] = False
            
    threading.Thread(target=_do_test, daemon=True).start()

def _get_speedtest():
    now = time.time()
    if _speedtest_cache["d"] is None or (now - _speedtest_cache["t"] > 1800):
        _run_speedtest_bg()
    return _speedtest_cache["d"]

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

import json
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
    if code in (0, 1): return WMO_ART["clear"]
    if code == 2: return WMO_ART["partly"]
    if code == 3: return WMO_ART["cloudy"]
    if code in (45, 48): return WMO_ART["fog"]
    if code in (51, 53, 55, 56, 57): return WMO_ART["drizzle"]
    if code in (61, 63, 80, 81): return WMO_ART["rain"]
    if code in (65, 66, 67, 82): return WMO_ART["heavy_rain"]
    if code in (71, 73, 75, 77, 85, 86): return WMO_ART["snow"]
    if code in (95, 96, 99): return WMO_ART["thunder"]
    return WMO_ART["cloudy"]

def _weather():
    now = time.time()
    if _weather_cache["d"] and now - _weather_cache["t"] < 300:
        return _weather_cache["d"]
    try:
        loc = json.loads(urllib.request.urlopen("https://ipapi.co/json/", timeout=6).read().decode())
        lat, lon = loc.get("latitude"), loc.get("longitude")
        if lat is None: return None
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,apparent_temperature,weather_code"
            f"&temperature_unit=fahrenheit"
        )
        data = json.loads(urllib.request.urlopen(url, timeout=8).read().decode())
        cur = data.get("current", {})
        code = int(cur.get("weather_code", 3))
        w = {
            "temp": round(float(cur.get("temperature_2m", 0))),
            "feels": round(float(cur.get("apparent_temperature", 0))),
            "desc": WMO_DESC.get(code, "conditions"),
            "code": code,
        }
        _weather_cache.update(d=w, t=now)
        return w
    except Exception:
        return None


# ── snapshot (collect once) ───────────────
def _collect():
    cpu = psutil.cpu_percent(interval=0)
    _cpu_hist.append(cpu)
    if len(_cpu_hist) > 60: _cpu_hist.pop(0)

    up_rate, down_rate = _net()
    _net_hist.append(up_rate + down_rate)
    if len(_net_hist) > 60: _net_hist.pop(0)

    _snap.update(
        cpu=cpu,
        cpu_h=list(_cpu_hist),
        ram=psutil.virtual_memory(),
        disk=psutil.disk_usage("C:/"),
        sent=up_rate, recv=down_rate,
        net_d=[max(0, _net_hist[i] - _net_hist[i-1]) for i in range(1, len(_net_hist))],
        speedtest=_get_speedtest(),
        procs=_procs(),
        weather=_weather(),
        now=datetime.now(),
    )


# ── drawing primitives ─────────────────────────────────
def _render(out, W, H, cfg):
    thm = cfg["themes"][cfg["theme"]]
    
    def tup(k):
        return tuple(thm[k])
    
    BG = tup("bg")
    GRID = tup("grid")
    DIM = tup("dim")
    MID = tup("mid")
    BRIGHT = tup("bright")
    WHITE = tup("white")
    BAR_BG = tup("bar_bg")
    BAR_FILL = tup("bar_fill")
    GRAPH_BAR = tup("graph")

    now = _snap.get("now", datetime.now())
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    for y in range(0, H, 32):
        for x in range(0, W, 32):
            d.point((x, y), fill=GRID)

    f12 = _font(12)
    f14 = _font(14)
    f16 = _font(16)
    f18 = _font(18)
    f32 = _font(32, bold=True)

    def _frame(x, y, w, h, title):
        d.rectangle((x, y, x + w, y + h), outline=DIM)
        t = f" {title} "
        tw = d.textlength(t, font=f16)
        d.rectangle((x + 16, y - 11, x + 18 + tw, y + 11), fill=BG)
        d.text((x + 17, y - 9), t, font=f16, fill=WHITE)

    def _bar(x, y, w, pct, h=14):
        d.rectangle((x, y, x + w, y + h), fill=BAR_BG, outline=DIM)
        fill = max(0, int((w - 4) * min(max(pct, 0), 100) / 100))
        if fill > 0:
            block_w = 4
            gap = 2
            for bx in range(2, fill, block_w + gap):
                seg_w = min(block_w, fill - bx)
                if seg_w > 0:
                    d.rectangle((x + bx, y + 2, x + bx + seg_w, y + h - 2), fill=BAR_FILL)

    def _spark(x, y, vals, w, h):
        if len(vals) < 2: return
        mx = max(max(vals), 1)
        bw = max(2, w // len(vals))
        for i, v in enumerate(vals):
            bh = max(1, int((v / mx) * h))
            bx = x + i * bw
            d.rectangle((bx, y + h - bh, bx + bw - 2, y + h), fill=GRAPH_BAR)

    mods = cfg["modules"]
    
    mx = int(W * 0.1)
    top = 240
    gap = 80
    cw = (W - mx * 2 - gap) // 2
    lx, rx = mx, mx + cw + gap
    pad = 24
    inner = cw - pad * 2

    # ── LEFT COLUMN ──────────────────────────────
    ly = top
    
    if mods.get("system", True):
        _frame(lx, ly, cw, 210, "SYSTEM")
        iy = ly + 32
        d.text((lx + pad, iy), _cpu_name(), font=f18, fill=WHITE)
        d.text((lx + cw - 68, iy), f"{_snap.get('cpu', 0):.0f}%", font=f18, fill=WHITE)
        iy += 32
        _bar(lx + pad, iy, inner, _snap.get('cpu', 0))
        iy += 24
        d.rectangle((lx + pad, iy, lx + pad + inner, iy + 46), fill=BAR_BG)
        _spark(lx + pad, iy, _snap.get("cpu_h", []), inner, 46)
        iy += 62
        d.text((lx + pad, iy), f"gpu:  {_gpu_name()}", font=f14, fill=MID)
        iy += 20
        d.text((lx + pad, iy), f"up:   {_uptime()}    os:  {_os_name()}", font=f14, fill=MID)
        ly += 240

    if mods.get("memory", True):
        _frame(lx, ly, cw, 105, "MEMORY")
        iy = ly + 32
        ram = _snap.get("ram", psutil.virtual_memory())
        ug = ram.used / (1024**3)
        d.text((lx + pad, iy), f"{_fmt_stor(ug)} / {_ram_total()}", font=f18, fill=WHITE)
        d.text((lx + cw - 68, iy), f"{ram.percent:.0f}%", font=f18, fill=WHITE)
        iy += 32
        _bar(lx + pad, iy, inner, ram.percent)
        ly += 135

    if mods.get("storage", True):
        _frame(lx, ly, cw, 105, "STORAGE")
        iy = ly + 32
        disk = _snap.get("disk", psutil.disk_usage("C:/"))
        ug = (disk.total - disk.free) / (1024**3)
        d.text((lx + pad, iy), f"C:\\  {_fmt_stor(ug)} / {_disk_total()}", font=f18, fill=WHITE)
        d.text((lx + cw - 68, iy), f"{disk.percent:.0f}%", font=f18, fill=WHITE)
        iy += 32
        _bar(lx + pad, iy, inner, disk.percent)
        ly += 135


    # ── RIGHT COLUMN ──────────────────────────────────
    ry = top
    
    if mods.get("weather", True):
        _frame(rx, ry, cw, 175, "WEATHER")
        weather = _snap.get("weather")
        if weather:
            ay = ry + 25
            for line in _wmo_art(weather["code"]):
                d.text((rx + pad, ay), line, font=f16, fill=MID)
                ay += 20
            d.text((rx + 220, ry + 45), f"{weather['temp']}F", font=f32, fill=WHITE)
            d.text((rx + 222, ry + 95), weather["desc"], font=f16, fill=BRIGHT)
            feels = weather.get("feels", weather["temp"])
            d.text((rx + 222, ry + 120), f"feels {feels}F", font=f14, fill=DIM)
        else:
            d.text((rx + pad, ry + 60), "no data", font=f16, fill=DIM)
        ry += 205

    if mods.get("network", True):
        _frame(rx, ry, cw, 125, "NETWORK")
        iy = ry + 32
        st = _snap.get("speedtest")
        if st:
            d.text((rx + pad, iy), "dl:", font=f14, fill=DIM)
            d.text((rx + pad + 30, iy), f"{st['down']:.1f} Mbps", font=f18, fill=WHITE)
            d.text((rx + cw // 2, iy), "ul:", font=f14, fill=DIM)
            d.text((rx + cw // 2 + 30, iy), f"{st['up']:.1f} Mbps", font=f18, fill=WHITE)
        else:
            d.text((rx + pad, iy), "testing...", font=f14, fill=DIM)
        
        iy += 40
        d.rectangle((rx + pad, iy, rx + pad + inner, iy + 35), fill=BAR_BG)
        _spark(rx + pad, iy, _snap.get("net_d", []), inner, 35)
        ry += 155

    if mods.get("processes", True):
        # We assume 120 height to make total height 480 (175+30+125+30+120=480)
        _frame(rx, ry, cw, 120, "PROCESSES")
        iy = ry + 28
        d.text((rx + pad, iy), f"{'NAME':<22}{'CPU':>7} {'MEM':>7}", font=f12, fill=DIM)
        iy += 22
        procs = _snap.get("procs", [])
        if not procs:
            d.text((rx + pad, iy), "sampling...", font=f12, fill=DIM)
        for name, cp, mm in procs[:3]:
            c = BRIGHT if cp > 2 else MID
            d.text((rx + pad, iy), f"{name[:20]:<22}{cp:6.1f}% {mm:6.1f}%", font=f12, fill=c)
            iy += 18
        ry += 150

    # ── DECORATIONS ─────────────────────────────────────
    d.text((mx - 10, top - 20), "+----", font=f10 := _font(10), fill=DIM)
    d.text((W - mx - 25, top - 20), "----+", font=f10, fill=DIM)
    
    bot_y = max(ly, ry) - 30 + 10
    d.text((mx - 10, bot_y), "+----", font=f10, fill=DIM)
    d.text((W - mx - 25, bot_y), "----+", font=f10, fill=DIM)

    # center pipe
    pipe_x = lx + cw + gap // 2
    for yp in range(top, bot_y, 24):
        d.text((pipe_x, yp), "|", font=f12, fill=DIM)

    # ── BOTTOM STAMP ────────────────────────────────────
    fmt = "%I:%M:%S %p" if cfg["behavior"].get("time_format", "12-hour") == "12-hour" else "%H:%M:%S"
    stamp = f"updated {now.strftime(fmt)}  |  {cfg['behavior']['interval']}s"
    tw = d.textlength(stamp, font=f14)
    d.text(((W - tw) / 2, H - 100), stamp, font=f14, fill=DIM)

    img.save(out)


# ── Windows Integration ────────────────────────────────
def _apply_wall(p):
    ctypes.windll.user32.SystemParametersInfoW(0x0014, 0, str(p), 0x01 | 0x02)

def _apply_lock(bmp, cfg):
    if not cfg["behavior"]["lockscreen_enabled"]:
        return
    try:
        import winreg
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

def _disable_fade(cfg):
    if not cfg["behavior"]["disable_fade"]:
        return
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(k, "WallpaperTransitionMode", 0, winreg.REG_DWORD, 0)
        winreg.SetValueEx(k, "WallpaperStyle", 0, winreg.REG_SZ, "10")
        winreg.SetValueEx(k, "TileWallpaper", 0, winreg.REG_SZ, "0")
        winreg.CloseKey(k)
        k2 = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(k2, "EnableTransparentGlass", 0, winreg.REG_DWORD, 1)
        winreg.CloseKey(k2)
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

    try:
        log.write_text("", encoding="utf-8")
        _log("started")
    except Exception:
        pass

    cfg = load_config()

    _install_startup(proj)
    _disable_fade(cfg)

    W, H = _screen()

    # Generate solid black lockscreen once
    lock_img = Image.new("RGB", (W, H), tuple(cfg["themes"][cfg["theme"]]["bg"]))
    lock_img.save(lock)
    _apply_lock(lock, cfg)
    _log("lockscreen set")

    # Immediate first render
    try:
        _collect()
        _render(wall, W, H, cfg)
        _apply_wall(wall)
        _log("first render ok")
    except Exception as e:
        _log(f"first render err: {e}")

    while True:
        try:
            cfg = load_config()
            _collect()
            _render(wall, W, H, cfg)
            _apply_wall(wall)
            _log("ok")
        except Exception as e:
            _log(f"err: {e}")
        time.sleep(cfg["behavior"]["interval"])


if __name__ == "__main__":
    main()
