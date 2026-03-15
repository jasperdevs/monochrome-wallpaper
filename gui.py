"""
monochrome-wallpaper settings GUI
Clean, single-page, native Windows 11 Fluent interface.
"""
import sys
import subprocess
import time
from pathlib import Path
import psutil

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QHBoxLayout, QWidget, QFrame
from qfluentwidgets import (
    setTheme, Theme, setThemeColor,
    SubtitleLabel, BodyLabel, SpinBox, SwitchButton, PrimaryPushButton,
    CardWidget, VBoxLayout, StrongBodyLabel, InfoBar, InfoBarPosition,
    ScrollArea, ComboBox, PushButton, FluentWindow, NavigationItemPosition
)

from config_manager import load_config, save_config

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
        except:
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
        except:
            pass


class SettingsInterface(ScrollArea):
    def __init__(self, cfg, parent=None):
        super().__init__(parent=parent)
        self.cfg = cfg
        self.view = QWidget(self)
        self.layout = VBoxLayout(self.view)
        
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.setObjectName("settingsInterface")
        self.view.setObjectName("view")
        
        self.layout.setContentsMargins(36, 24, 36, 24)
        self.layout.setSpacing(24)

        # Huge title like Windows 11 Settings
        title = SubtitleLabel("Dashboard Settings", self.view)
        self.layout.addWidget(title)

        # --- STATUS CARD ---
        self.statusCard = CardWidget(self.view)
        sl = QHBoxLayout(self.statusCard)
        sl.setContentsMargins(20, 20, 20, 20)
        
        text_layout = QVBoxLayout()
        text_layout.addWidget(StrongBodyLabel("Service Status", self.statusCard))
        self.status_desc = BodyLabel("Checking...", self.statusCard)
        text_layout.addWidget(self.status_desc)
        sl.addLayout(text_layout)
        sl.addStretch()
        
        self.toggle_btn = PushButton("Start", self.statusCard)
        self.toggle_btn.clicked.connect(self._toggle)
        sl.addWidget(self.toggle_btn)
        self.layout.addWidget(self.statusCard)

        # --- BEHAVIOR CARD ---
        self.layout.addWidget(StrongBodyLabel("System Behavior", self.view))
        self.behaviorCard = CardWidget(self.view)
        bl = QVBoxLayout(self.behaviorCard)
        bl.setContentsMargins(20, 16, 20, 16)
        bl.setSpacing(16)

        il = QHBoxLayout()
        il.addWidget(BodyLabel("Refresh Interval", self.behaviorCard))
        il.addStretch()
        self.interval_spin = SpinBox(self.behaviorCard)
        self.interval_spin.setRange(5, 300)
        self.interval_spin.setValue(self.cfg["behavior"]["interval"])
        self.interval_spin.setSuffix(" sec")
        il.addWidget(self.interval_spin)
        bl.addLayout(il)

        sep1 = QFrame(self.behaviorCard)
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("background-color: #333333; border: none;")
        sep1.setFixedHeight(1)
        bl.addWidget(sep1)

        fl = QHBoxLayout()
        fl.addWidget(BodyLabel("Disable Windows crossfade animation", self.behaviorCard))
        fl.addStretch()
        self.fade_switch = SwitchButton(self.behaviorCard)
        self.fade_switch.setChecked(self.cfg["behavior"]["disable_fade"])
        fl.addWidget(self.fade_switch)
        bl.addLayout(fl)

        sep2 = QFrame(self.behaviorCard)
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("background-color: #333333; border: none;")
        sep2.setFixedHeight(1)
        bl.addWidget(sep2)

        ll = QHBoxLayout()
        ll.addWidget(BodyLabel("Enable solid-color lockscreen override", self.behaviorCard))
        ll.addStretch()
        self.lock_switch = SwitchButton(self.behaviorCard)
        self.lock_switch.setChecked(self.cfg["behavior"].get("lockscreen_enabled", True))
        ll.addWidget(self.lock_switch)
        bl.addLayout(ll)
        
        sep3 = QFrame(self.behaviorCard)
        sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setStyleSheet("background-color: #333333; border: none;")
        sep3.setFixedHeight(1)
        bl.addWidget(sep3)
        
        tf_layout = QHBoxLayout()
        tf_layout.addWidget(BodyLabel("Time Format", self.behaviorCard))
        tf_layout.addStretch()
        self.time_combo = ComboBox(self.behaviorCard)
        self.time_combo.addItems(["12-hour", "24-hour"])
        self.time_combo.setCurrentText(self.cfg["behavior"].get("time_format", "12-hour"))
        tf_layout.addWidget(self.time_combo)
        bl.addLayout(tf_layout)

        self.layout.addWidget(self.behaviorCard)

        # --- APPEARANCE CARD ---
        self.layout.addWidget(StrongBodyLabel("Visual Configuration", self.view))
        self.appearanceCard = CardWidget(self.view)
        al = QVBoxLayout(self.appearanceCard)
        al.setContentsMargins(20, 16, 20, 16)
        al.setSpacing(16)

        tl = QHBoxLayout()
        tl.addWidget(BodyLabel("Color Theme", self.appearanceCard))
        tl.addStretch()
        self.theme_combo = ComboBox(self.appearanceCard)
        self.theme_combo.addItems(list(self.cfg["themes"].keys()))
        self.theme_combo.setCurrentText(self.cfg["theme"])
        tl.addWidget(self.theme_combo)
        al.addLayout(tl)

        self.layout.addWidget(self.appearanceCard)

        # --- MODULES CARD ---
        self.layout.addWidget(StrongBodyLabel("Active Modules", self.view))
        self.modulesCard = CardWidget(self.view)
        ml = QVBoxLayout(self.modulesCard)
        ml.setContentsMargins(20, 16, 20, 16)
        ml.setSpacing(16)

        self.mod_switches = {}
        for i, (mod, val) in enumerate(self.cfg["modules"].items()):
            row = QHBoxLayout()
            row.addWidget(BodyLabel(mod.capitalize(), self.modulesCard))
            row.addStretch()
            sw = SwitchButton(self.modulesCard)
            sw.setChecked(val)
            self.mod_switches[mod] = sw
            row.addWidget(sw)
            ml.addLayout(row)
            
            # Don't add a separator after the last item
            if i < len(self.cfg["modules"]) - 1:
                sep = QFrame(self.modulesCard)
                sep.setFrameShape(QFrame.Shape.HLine)
                sep.setStyleSheet("background-color: #333333; border: none;")
                sep.setFixedHeight(1)
                ml.addWidget(sep)

        self.layout.addWidget(self.modulesCard)

        self.layout.addStretch()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_status)
        self.timer.start(2000)
        self._refresh_status()

    def _refresh_status(self):
        if is_running():
            self.status_desc.setText("Running securely in background")
            self.status_desc.setStyleSheet("color: #d0d0d0;")
            self.toggle_btn.setText("Stop")
        else:
            self.status_desc.setText("Service is stopped")
            self.status_desc.setStyleSheet("color: #9a9a9a;")
            self.toggle_btn.setText("Start")

    def _toggle(self):
        if is_running():
            stop_wallpaper()
        else:
            start_wallpaper()
        time.sleep(0.5)
        self._refresh_status()

    def update_cfg(self):
        self.cfg["behavior"]["interval"] = self.interval_spin.value()
        self.cfg["behavior"]["disable_fade"] = self.fade_switch.isChecked()
        self.cfg["behavior"]["lockscreen_enabled"] = self.lock_switch.isChecked()
        self.cfg["behavior"]["time_format"] = self.time_combo.currentText()
        self.cfg["theme"] = self.theme_combo.currentText()
        for mod, sw in self.mod_switches.items():
            self.cfg["modules"][mod] = sw.isChecked()


class Window(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dashboard Settings")
        self.resize(550, 650)
        
        self.cfg = load_config()

        # Hide the sidebar navigation entirely!
        self.navigationInterface.hide()

        self.settingsInterface = SettingsInterface(self.cfg, self)
        
        # In FluentWindow, if we don't want navigation, we just set the widget directly
        # to the stacked widget area.
        self.addSubInterface(self.settingsInterface, None, "Settings")
        
        # Add Apply button floating at the bottom right
        self.apply_btn = PrimaryPushButton("Apply Changes", self)
        self.apply_btn.setFixedSize(140, 36)
        self.apply_btn.move(self.width() - 170, self.height() - 60)
        self.apply_btn.clicked.connect(self._apply_settings)
        
        # Handle resize to keep button docked
        self.resizeEvent = self._on_resize

    def _on_resize(self, event):
        super().resizeEvent(event)
        self.apply_btn.move(self.width() - 170, self.height() - 60)

    def _apply_settings(self):
        self.settingsInterface.update_cfg()
        save_config(self.cfg)
        
        if is_running():
            stop_wallpaper()
            time.sleep(1)
            start_wallpaper()

        InfoBar.success(
            title='Success',
            content="Settings saved and applied instantly.",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )


def main():
    setTheme(Theme.DARK)
    setThemeColor("#8a8a8a")
    app = QApplication(sys.argv)
    w = Window()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
