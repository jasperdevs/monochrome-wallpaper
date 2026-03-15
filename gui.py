"""
monochrome-wallpaper settings GUI
"""

import subprocess
import sys
from pathlib import Path

import psutil
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSpinBox, QGroupBox, QFrame,
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


def get_interval():
    try:
        text = SCRIPT.read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith("INTERVAL"):
                return int(line.split("=")[1].strip())
    except Exception:
        pass
    return 15


def set_interval(val):
    try:
        text = SCRIPT.read_text(encoding="utf-8")
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("INTERVAL"):
                lines[i] = f"INTERVAL = {val}"
                break
        SCRIPT.write_text("\n".join(lines), encoding="utf-8")
        # Restart if running
        if is_running():
            stop_wallpaper()
            import time
            time.sleep(1)
            start_wallpaper()
    except Exception:
        pass


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("monochrome-wallpaper")
        self.setFixedSize(420, 340)
        self._apply_theme()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Title
        title = QLabel("monochrome-wallpaper")
        title.setFont(QFont("Cascadia Mono", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #e0e0e0;")
        layout.addWidget(title)

        subtitle = QLabel("live system dashboard wallpaper")
        subtitle.setFont(QFont("Cascadia Mono", 10))
        subtitle.setStyleSheet("color: #888;")
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        # Status
        status_group = QGroupBox("Status")
        status_group.setFont(QFont("Cascadia Mono", 10))
        status_layout = QHBoxLayout(status_group)

        self.status_label = QLabel("checking...")
        self.status_label.setFont(QFont("Cascadia Mono", 11))
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        self.toggle_btn = QPushButton("Start")
        self.toggle_btn.setFixedWidth(100)
        self.toggle_btn.setFont(QFont("Cascadia Mono", 10))
        self.toggle_btn.clicked.connect(self._toggle)
        status_layout.addWidget(self.toggle_btn)

        layout.addWidget(status_group)

        # Interval
        interval_group = QGroupBox("Refresh Interval")
        interval_group.setFont(QFont("Cascadia Mono", 10))
        interval_layout = QHBoxLayout(interval_group)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(5, 300)
        self.interval_spin.setSuffix("s")
        self.interval_spin.setValue(get_interval())
        self.interval_spin.setFont(QFont("Cascadia Mono", 11))
        self.interval_spin.setFixedWidth(100)
        interval_layout.addWidget(self.interval_spin)

        apply_btn = QPushButton("Apply")
        apply_btn.setFixedWidth(80)
        apply_btn.setFont(QFont("Cascadia Mono", 10))
        apply_btn.clicked.connect(self._apply_interval)
        interval_layout.addWidget(apply_btn)

        interval_layout.addStretch()
        layout.addWidget(interval_group)

        layout.addStretch()

        # Footer
        footer = QLabel("github.com/jasprcodess/monochrome-wallpaper")
        footer.setFont(QFont("Cascadia Mono", 9))
        footer.setStyleSheet("color: #555;")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer)

        # Timer to refresh status
        self.timer = QTimer()
        self.timer.timeout.connect(self._refresh)
        self.timer.start(2000)
        self._refresh()

    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #161616; }
            QGroupBox {
                border: 1px solid #333;
                border-radius: 4px;
                margin-top: 12px;
                padding-top: 16px;
                color: #aaa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
            QPushButton {
                background-color: #2a2a2a;
                color: #ddd;
                border: 1px solid #444;
                border-radius: 3px;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #333; }
            QPushButton:pressed { background-color: #444; }
            QSpinBox {
                background-color: #222;
                color: #ddd;
                border: 1px solid #444;
                border-radius: 3px;
                padding: 4px 8px;
            }
            QLabel { color: #ccc; }
        """)

    def _refresh(self):
        running = is_running()
        if running:
            self.status_label.setText("running")
            self.status_label.setStyleSheet("color: #8f8;")
            self.toggle_btn.setText("Stop")
        else:
            self.status_label.setText("stopped")
            self.status_label.setStyleSheet("color: #f88;")
            self.toggle_btn.setText("Start")

    def _toggle(self):
        if is_running():
            stop_wallpaper()
        else:
            start_wallpaper()
        import time
        time.sleep(1)
        self._refresh()

    def _apply_interval(self):
        set_interval(self.interval_spin.value())


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
