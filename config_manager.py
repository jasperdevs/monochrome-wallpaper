import json
from pathlib import Path

DEFAULT_CONFIG = {
    "behavior": {
        "interval": 15,
        "disable_fade": True,
        "lockscreen_enabled": True,
        "time_format": "12-hour"
    },
    "theme": "Monochrome",
    "themes": {
        "Monochrome": {
            "bg": [16, 16, 16],
            "grid": [28, 28, 28],
            "dim": [80, 80, 80],
            "mid": [140, 140, 140],
            "bright": [215, 215, 215],
            "white": [245, 245, 245],
            "bar_bg": [30, 30, 30],
            "bar_fill": [100, 100, 100],
            "graph": [90, 90, 90]
        },
        "Matrix": {
            "bg": [10, 15, 10],
            "grid": [15, 25, 15],
            "dim": [30, 80, 30],
            "mid": [40, 140, 40],
            "bright": [80, 210, 80],
            "white": [150, 255, 150],
            "bar_bg": [15, 30, 15],
            "bar_fill": [50, 160, 50],
            "graph": [40, 180, 40]
        },
        "Nord": {
            "bg": [46, 52, 64],
            "grid": [59, 66, 82],
            "dim": [76, 86, 106],
            "mid": [129, 161, 193],
            "bright": [136, 192, 208],
            "white": [236, 239, 244],
            "bar_bg": [59, 66, 82],
            "bar_fill": [143, 188, 187],
            "graph": [129, 161, 193]
        },
        "Cyberpunk": {
            "bg": [20, 10, 30],
            "grid": [40, 15, 50],
            "dim": [120, 40, 100],
            "mid": [210, 80, 180],
            "bright": [255, 113, 206],
            "white": [1, 255, 255],
            "bar_bg": [50, 20, 60],
            "bar_fill": [255, 255, 0],
            "graph": [255, 113, 206]
        }
    },
    "modules": {
        "system": True,
        "memory": True,
        "storage": True,
        "weather": True,
        "network": True,
        "processes": True
    }
}

CONFIG_PATH = Path(__file__).parent / "config.json"

def load_config():
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_CONFIG

def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=4)
