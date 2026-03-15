"""
monochrome-wallpaper settings GUI
"""

import subprocess
import sys
from pathlib import Path

import psutil
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon, QCursor
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSpinBox, QGroupBox, QCheckBox, QFrame,
    QFormLayout
)

PROJ = Path(__file__).parent
SCRIPT = PROJ / "generate_wallpaper.py"
PYTHONW = sys.executable.replace("python.exe", "pythonw.exe")
if not Path(PYTHONW).exists():
    PYTHONW = sys.executable


def is_running():
    for p in psutil.process_iter(["name", "cmdline"]):
        try:
            cmd = " ".join(p.info.get("cmdline") or [])
            if "generate_wallpaper.py" in cmd and "python" in (p.info.get("name") or "").lower():
                if "gui.py" not in cmd:
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False


def start_wallpaper():
    subprocess.Popen(
        [PYTHONW, str(SCRIPT)],
        cwd=str(PROJ),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
    )


def stop_wallpaper():
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmd = " ".join(p.info.get("cmdline") or [])
            if "generate_wallpaper.py" in cmd and "python" in (p.info.get("name") or "").lower():
                if "gui.py" not in cmd:
                    p.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass


def get_config():
    config = {
        "interval": 15,
        "disable_fade": True,
        "show_time": True
    }
    try:
        text = SCRIPT.read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("INTERVAL ="):
                config["interval"] = int(line.split("=")[1].strip())
            elif line.startswith("DISABLE_FADE ="):
                config["disable_fade"] = line.split("=")[1].strip() == "True"
            elif line.startswith("SHOW_TIME ="):
                config["show_time"] = line.split("=")[1].strip() == "True"
    except Exception:
        pass
    return config


def save_config(config):
    try:
        text = SCRIPT.read_text(encoding="utf-8")
        lines = text.splitlines()
        for i, line in enumerate(lines):
            l = line.strip()
            if l.startswith("INTERVAL ="):
                lines[i] = f"INTERVAL = {config['interval']}"
            elif l.startswith("DISABLE_FADE ="):
                lines[i] = f"DISABLE_FADE = {config['disable_fade']}"
            elif l.startswith("SHOW_TIME ="):
                lines[i] = f"SHOW_TIME = {config['show_time']}"
        SCRIPT.write_text("\n".join(lines), encoding="utf-8")
        
        if is_running():
            stop_wallpaper()
            import time
            time.sleep(1)
            start_wallpaper()
    except Exception as e:
        print(f"Error saving config: {e}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Monochrome Wallpaper Settings")
        self.setFixedSize(400, 480)
        self._apply_theme()

        self.cfg = get_config()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Header
        header_layout = QHBoxLayout()
        title = QLabel("Monochrome")
        title.setFont(QFont("Cascadia Mono", 20, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff;")
        
        self.status_dot = QLabel("●")
        self.status_dot.setFont(QFont("Arial", 16))
        
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.status_dot)
        layout.addLayout(header_layout)

        subtitle = QLabel("Live system dashboard wallpaper")
        subtitle.setFont(QFont("Cascadia Mono", 10))
        subtitle.setStyleSheet("color: #888888;")
        layout.addWidget(subtitle)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #333333;")
        layout.addWidget(sep)

        # Settings
        form_layout = QFormLayout()
        form_layout.setSpacing(15)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(5, 300)
        self.interval_spin.setSuffix(" sec")
        self.interval_spin.setValue(self.cfg["interval"])
        self.interval_spin.setFont(QFont("Cascadia Mono", 10))
        self.interval_spin.setFixedWidth(100)
        
        int_label = QLabel("Refresh Interval:")
        int_label.setFont(QFont("Cascadia Mono", 10))
        form_layout.addRow(int_label, self.interval_spin)

        self.fade_check = QCheckBox("Disable Windows Wallpaper Fade")
        self.fade_check.setFont(QFont("Cascadia Mono", 10))
        self.fade_check.setChecked(self.cfg["disable_fade"])
        form_layout.addRow("", self.fade_check)

        self.time_check = QCheckBox("Show Time & Date")
        self.time_check.setFont(QFont("Cascadia Mono", 10))
        self.time_check.setChecked(self.cfg["show_time"])
        form_layout.addRow("", self.time_check)

        layout.addLayout(form_layout)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.toggle_btn = QPushButton("Start Wallpaper")
        self.toggle_btn.setFont(QFont("Cascadia Mono", 11, QFont.Weight.Bold))
        self.toggle_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.toggle_btn.clicked.connect(self._toggle)
        btn_layout.addWidget(self.toggle_btn)

        self.apply_btn = QPushButton("Apply Settings")
        self.apply_btn.setFont(QFont("Cascadia Mono", 11, QFont.Weight.Bold))
        self.apply_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.apply_btn.clicked.connect(self._apply_settings)
        btn_layout.addWidget(self.apply_btn)

        layout.addLayout(btn_layout)

        self.timer = QTimer()
        self.timer.timeout.connect(self._refresh_status)
        self.timer.start(1500)
        self._refresh_status()

    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #121212; }
            QLabel { color: #cccccc; }
            QSpinBox {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #333333;
                border-radius: 4px;
                padding: 6px;
            }
            QSpinBox::up-button, QSpinBox::down-button { width: 0px; }
            QCheckBox { color: #cccccc; }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                background-color: #1e1e1e;
                border: 1px solid #333333;
                border-radius: 4px;
            }
            QCheckBox::indicator:checked {
                background-color: #555555;
                border: 1px solid #777777;
            }
            QPushButton {
                background-color: #222222;
                color: #ffffff;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 10px;
            }
            QPushButton:hover { background-color: #333333; border: 1px solid #555555; }
            QPushButton:pressed { background-color: #111111; }
        """)

    def _refresh_status(self):
        if is_running():
            self.status_dot.setStyleSheet("color: #4CAF50;")
            self.status_dot.setToolTip("Running")
            self.toggle_btn.setText("Stop")
            self.toggle_btn.setStyleSheet("background-color: #3d1b1b; border-color: #5c2828; color: #ffb3b3;")
        else:
            self.status_dot.setStyleSheet("color: #F44336;")
            self.status_dot.setToolTip("Stopped")
            self.toggle_btn.setText("Start")
            self.toggle_btn.setStyleSheet("")

    def _toggle(self):
        if is_running():
            stop_wallpaper()
        else:
            start_wallpaper()
        import time
        time.sleep(0.5)
        self._refresh_status()

    def _apply_settings(self):
        self.cfg["interval"] = self.interval_spin.value()
        self.cfg["disable_fade"] = self.fade_check.isChecked()
        self.cfg["show_time"] = self.time_check.isChecked()
        save_config(self.cfg)
        self.apply_btn.setText("Applied!")
        QTimer.singleShot(1500, lambda: self.apply_btn.setText("Apply Settings"))


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
