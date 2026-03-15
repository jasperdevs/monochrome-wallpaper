# monochrome-wallpaper

Live-updating monochrome desktop wallpaper that shows real system info.

Auto-detects your hardware, OS, uptime, and installed dev tools.
Refreshes on an interval and reapplies itself. No personal data is hardcoded.

## Requirements

- Windows 10/11
- Python 3.10+
- `pip install Pillow`
- A monospace font (Cascadia Mono preferred, falls back to Consolas)

## Usage

```bash
python generate_wallpaper.py
```

Runs in a loop, regenerating and applying the wallpaper every 60 seconds.
Edit `INTERVAL` at the top of the script to change the refresh rate.

## What it shows

- Username and hostname
- Time and date
- CPU, GPU, RAM, disk usage
- OS version and uptime
- Installed dev tools (node, python, git, docker, etc.)

## Config

All constants are at the top of `generate_wallpaper.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `INTERVAL` | `60` | Seconds between refreshes |
| `BG` | `(22,22,22)` | Background color (`#161616`) |
| `FONT_NAME` | `CascadiaMono.ttf` | Primary font |
