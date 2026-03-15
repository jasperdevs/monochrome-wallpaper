"""
monochrome-wallpaper settings GUI
Native Windows styling.
"""

import subprocess
import sys
from pathlib import Path

import psutil
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSpinBox, QGroupBox, QCheckBox,
    QFormLayout, QMessageBox
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
        "disable_fade": True
    }
    try:
        text = SCRIPT.read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("INTERVAL ="):
                config["interval"] = int(line.split("=")[1].strip())
            elif line.startswith("DISABLE_FADE ="):
                config["disable_fade"] = line.split("=")[1].strip() == "True"
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
        SCRIPT.write_text("\n".join(lines), encoding="utf-8")
        
        if is_running():
            stop_wallpaper()
            import time
            time.sleep(1)
            start_wallpaper()
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Monochrome Wallpaper Settings")
        self.setFixedSize(380, 260)
        
        # Native Windows font
        app_font = QFont("Segoe UI", 9)
        QApplication.setFont(app_font)

        self.cfg = get_config()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header / Status
        header_layout = QHBoxLayout()
        title = QLabel("monochrome-wallpaper")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        self.status_label = QLabel("Checking status...")
        self.status_label.setStyleSheet("color: gray;")
        header_layout.addWidget(self.status_label)
        
        layout.addLayout(header_layout)

        # Settings Group
        settings_group = QGroupBox("Configuration")
        form_layout = QFormLayout()
        form_layout.setContentsMargins(12, 16, 12, 12)
        form_layout.setSpacing(10)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(5, 300)
        self.interval_spin.setSuffix(" seconds")
        self.interval_spin.setValue(self.cfg["interval"])
        form_layout.addRow("Refresh Interval:", self.interval_spin)

        self.fade_check = QCheckBox("Disable Windows wallpaper fade transition")
        self.fade_check.setChecked(self.cfg["disable_fade"])
        form_layout.addRow("", self.fade_check)

        settings_group.setLayout(form_layout)
        layout.addWidget(settings_group)
        
        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        
        self.toggle_btn = QPushButton("Start Wallpaper")
        self.toggle_btn.clicked.connect(self._toggle)
        btn_layout.addWidget(self.toggle_btn)
        
        btn_layout.addStretch()
        
        self.apply_btn = QPushButton("Apply Settings")
        self.apply_btn.setDefault(True)
        self.apply_btn.clicked.connect(self._apply_settings)
        btn_layout.addWidget(self.apply_btn)
        
        layout.addLayout(btn_layout)

        self.timer = QTimer()
        self.timer.timeout.connect(self._refresh_status)
        self.timer.start(2000)
        self._refresh_status()

    def _refresh_status(self):
        if is_running():
            self.status_label.setText("Running")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            self.toggle_btn.setText("Stop Wallpaper")
        else:
            self.status_label.setText("Stopped")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            self.toggle_btn.setText("Start Wallpaper")

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
        if save_config(self.cfg):
            self.apply_btn.setText("Applied")
            QTimer.singleShot(1500, lambda: self.apply_btn.setText("Apply Settings"))
        else:
            QMessageBox.critical(self, "Error", "Failed to save settings to generate_wallpaper.py")


def main():
    app = QApplication(sys.argv)
    # Use native Windows style instead of Fusion
    app.setStyle("windowsvista")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
