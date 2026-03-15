"""
monochrome-wallpaper settings GUI
Modern Windows 11 Fluent-style UI.
"""

import subprocess
import sys
from pathlib import Path

import psutil
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QFont, QIcon, QColor, QPalette, QCursor
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSpinBox, QGroupBox, QCheckBox,
    QFormLayout, QMessageBox, QFrame
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
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Monochrome Wallpaper Settings")
        self.setFixedSize(450, 420)
        
        # Fluent Design font
        app_font = QFont("Segoe UI Variable Display", 10)
        app_font.setStyleHint(QFont.StyleHint.SansSerif)
        QApplication.setFont(app_font)

        self.cfg = get_config()

        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)

        # Header Title
        title = QLabel("Monochrome Settings")
        title.setFont(QFont("Segoe UI Variable Display", 18, QFont.Weight.DemiBold))
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        # Status Card (Fluent Card UI)
        status_card = QFrame()
        status_card.setObjectName("fluentCard")
        status_layout = QHBoxLayout(status_card)
        status_layout.setContentsMargins(20, 16, 20, 16)
        
        self.status_icon = QLabel("●")
        self.status_icon.setFont(QFont("Segoe UI", 16))
        self.status_label = QLabel("Checking status...")
        self.status_label.setFont(QFont("Segoe UI Variable Display", 11, QFont.Weight.Medium))
        
        status_layout.addWidget(self.status_icon)
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        
        self.toggle_btn = QPushButton("Start")
        self.toggle_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.toggle_btn.setFixedSize(100, 36)
        self.toggle_btn.clicked.connect(self._toggle)
        status_layout.addWidget(self.toggle_btn)
        
        layout.addWidget(status_card)

        # Settings Card (Fluent Card UI)
        settings_card = QFrame()
        settings_card.setObjectName("fluentCard")
        form_layout = QFormLayout(settings_card)
        form_layout.setContentsMargins(20, 20, 20, 20)
        form_layout.setSpacing(20)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(5, 300)
        self.interval_spin.setSuffix(" sec")
        self.interval_spin.setValue(self.cfg["interval"])
        self.interval_spin.setFixedSize(100, 32)
        
        int_label = QLabel("Refresh Interval")
        int_label.setFont(QFont("Segoe UI Variable Display", 10))
        form_layout.addRow(int_label, self.interval_spin)

        self.fade_check = QCheckBox("Disable Windows wallpaper fade")
        self.fade_check.setChecked(self.cfg["disable_fade"])
        self.fade_check.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        form_layout.addRow("", self.fade_check)

        self.time_check = QCheckBox("Show Time & Date on wallpaper")
        self.time_check.setChecked(self.cfg.get("show_time", False))
        self.time_check.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        form_layout.addRow("", self.time_check)

        layout.addWidget(settings_card)
        
        layout.addStretch()

        # Apply Button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.apply_btn = QPushButton("Apply Settings")
        self.apply_btn.setObjectName("primaryButton")
        self.apply_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.apply_btn.setFixedSize(140, 36)
        self.apply_btn.clicked.connect(self._apply_settings)
        btn_layout.addWidget(self.apply_btn)
        
        layout.addLayout(btn_layout)

        self.timer = QTimer()
        self.timer.timeout.connect(self._refresh_status)
        self.timer.start(2000)
        self._refresh_status()
        self._apply_theme()

    def _apply_theme(self):
        # Modern Windows 11 Dark Mode styling (Mica-like colors, rounded corners)
        self.setStyleSheet("""
            QMainWindow, #centralWidget {
                background-color: #202020;
            }
            #titleLabel {
                color: #ffffff;
            }
            #fluentCard {
                background-color: #2b2b2b;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
            }
            QLabel {
                color: #e3e3e3;
            }
            QSpinBox {
                background-color: #333333;
                color: #ffffff;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 14px;
            }
            QSpinBox:hover {
                background-color: #3a3a3a;
                border: 1px solid #555555;
            }
            QCheckBox {
                color: #e3e3e3;
                font-size: 14px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                background-color: #333333;
                border: 1px solid #555555;
                border-radius: 4px;
            }
            QCheckBox::indicator:hover {
                background-color: #3a3a3a;
                border: 1px solid #777777;
            }
            QCheckBox::indicator:checked {
                background-color: #60cdff;
                border: 1px solid #60cdff;
                image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0iIzAwMDAwMCIgZD0iTTkgMTYuMTdMMDQuODMgMTJsLTEuNDIgMS40MUw5IDE5IDIxIDdsLTEuNDEtMS40MXoiLz48L3N2Zz4=);
            }
            QPushButton {
                background-color: #333333;
                color: #ffffff;
                border: 1px solid #444444;
                border-radius: 4px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
                border: 1px solid #555555;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
                border: 1px solid #333333;
                color: #aaaaaa;
            }
            #primaryButton {
                background-color: #60cdff;
                color: #000000;
                border: 1px solid #60cdff;
            }
            #primaryButton:hover {
                background-color: #55b6e6;
                border: 1px solid #55b6e6;
            }
            #primaryButton:pressed {
                background-color: #4a9ccc;
                border: 1px solid #4a9ccc;
                color: #333333;
            }
        """)

    def _refresh_status(self):
        if is_running():
            self.status_label.setText("Running securely in background")
            self.status_icon.setStyleSheet("color: #60cdff;")
            self.toggle_btn.setText("Stop")
        else:
            self.status_label.setText("Service is currently stopped")
            self.status_icon.setStyleSheet("color: #ff99a4;")
            self.toggle_btn.setText("Start")

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
        if save_config(self.cfg):
            self.apply_btn.setText("✓ Applied")
            QTimer.singleShot(2000, lambda: self.apply_btn.setText("Apply Settings"))
        else:
            QMessageBox.critical(self, "Error", "Failed to save settings.")


def main():
    # Attempt to enable high DPI scaling and use the native Windows look
    if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
        
    app = QApplication(sys.argv)
    
    # Apply a dark fusion base before our custom stylesheets
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
