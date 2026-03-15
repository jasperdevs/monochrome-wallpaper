"""
monochrome-wallpaper settings GUI
Modern Windows 11 Fluent-style UI using PyQt6-Fluent-Widgets.
"""

import subprocess
import sys
from pathlib import Path
import psutil

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QFont
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QHBoxLayout, QWidget
from qfluentwidgets import (
    setTheme, Theme, FluentWindow, NavigationItemPosition,
    SubtitleLabel, BodyLabel, SpinBox, SwitchButton, PrimaryPushButton,
    CardWidget, VBoxLayout, StrongBodyLabel, InfoBar, InfoBarPosition,
    ScrollArea, ExpandLayout
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


class SettingsInterface(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.view = QWidget(self)
        self.layout = VBoxLayout(self.view)
        
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.setObjectName("settingsInterface")
        
        self.view.setObjectName("view")
        self.layout.setContentsMargins(30, 20, 30, 20)
        self.layout.setSpacing(20)

        self.cfg = get_config()

        # Title
        self.titleLabel = SubtitleLabel("Monochrome Wallpaper Settings", self.view)
        self.layout.addWidget(self.titleLabel)

        # Status Card
        self.statusCard = CardWidget(self.view)
        status_layout = QHBoxLayout(self.statusCard)
        status_layout.setContentsMargins(20, 16, 20, 16)
        
        self.status_title = StrongBodyLabel("Service Status", self.statusCard)
        self.status_desc = BodyLabel("Checking...", self.statusCard)
        self.status_desc.setTextColor(QColor(150, 150, 150), QColor(150, 150, 150))
        
        text_layout = QVBoxLayout()
        text_layout.addWidget(self.status_title)
        text_layout.addWidget(self.status_desc)
        status_layout.addLayout(text_layout)
        
        status_layout.addStretch()
        
        self.toggle_btn = PrimaryPushButton("Start", self.statusCard)
        self.toggle_btn.clicked.connect(self._toggle)
        status_layout.addWidget(self.toggle_btn)
        
        self.layout.addWidget(self.statusCard)

        # Settings Card
        self.settingsCard = CardWidget(self.view)
        settings_layout = QVBoxLayout(self.settingsCard)
        settings_layout.setContentsMargins(20, 16, 20, 16)
        settings_layout.setSpacing(16)

        # Interval
        int_layout = QHBoxLayout()
        int_title = StrongBodyLabel("Refresh Interval", self.settingsCard)
        self.interval_spin = SpinBox(self.settingsCard)
        self.interval_spin.setRange(5, 300)
        self.interval_spin.setValue(self.cfg["interval"])
        self.interval_spin.setSuffix(" sec")
        
        int_layout.addWidget(int_title)
        int_layout.addStretch()
        int_layout.addWidget(self.interval_spin)
        settings_layout.addLayout(int_layout)

        # Separator inside card
        sep = QFrame(self.settingsCard)
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #333333; border: none;")
        sep.setFixedHeight(1)
        settings_layout.addWidget(sep)

        # Fade Toggle
        fade_layout = QHBoxLayout()
        fade_title = StrongBodyLabel("Disable Windows Fade", self.settingsCard)
        self.fade_switch = SwitchButton(self.settingsCard)
        self.fade_switch.setChecked(self.cfg["disable_fade"])
        
        fade_layout.addWidget(fade_title)
        fade_layout.addStretch()
        fade_layout.addWidget(self.fade_switch)
        settings_layout.addLayout(fade_layout)

        self.layout.addWidget(self.settingsCard)

        # Apply Button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.apply_btn = PrimaryPushButton("Apply Settings", self.view)
        self.apply_btn.clicked.connect(self._apply_settings)
        btn_layout.addWidget(self.apply_btn)
        self.layout.addLayout(btn_layout)

        self.layout.addStretch()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_status)
        self.timer.start(2000)
        self._refresh_status()

    def _refresh_status(self):
        if is_running():
            self.status_desc.setText("Running securely in background")
            self.status_desc.setStyleSheet("color: #60cdff;")
            self.toggle_btn.setText("Stop")
            # Style button as destructive/secondary when running
            self.toggle_btn.setStyleSheet("background-color: #3d1b1b; border-color: #5c2828; color: #ffb3b3;")
        else:
            self.status_desc.setText("Service is currently stopped")
            self.status_desc.setStyleSheet("color: #ff99a4;")
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
        self.cfg["disable_fade"] = self.fade_switch.isChecked()
        if save_config(self.cfg):
            InfoBar.success(
                title='Success',
                content="Settings applied successfully.",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
        else:
            InfoBar.error(
                title='Error',
                content="Failed to save settings.",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )


class Window(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Monochrome Settings")
        self.resize(500, 480)

        # create sub interface
        self.settingsInterface = SettingsInterface(self)
        
        self.addSubInterface(self.settingsInterface, None, "Settings")
        
        # We don't need the navigation panel for just one page
        self.navigationInterface.hide()


def main():
    setTheme(Theme.DARK)
    app = QApplication(sys.argv)
    
    # Create window
    w = Window()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
