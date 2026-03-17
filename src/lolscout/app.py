from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication


def _load_dotenv() -> None:
    candidate_paths: list[Path] = []

    cwd_env = Path.cwd() / ".env"
    candidate_paths.append(cwd_env)

    project_env = Path(__file__).resolve().parents[2] / ".env"
    if project_env not in candidate_paths:
        candidate_paths.append(project_env)

    executable_env = Path(sys.executable).resolve().parent / ".env"
    if executable_env not in candidate_paths:
        candidate_paths.append(executable_env)

    for env_path in candidate_paths:
        if not env_path.exists():
            continue

        try:
            lines = env_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue

        for raw_line in lines:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("\"'")
            if key:
                os.environ.setdefault(key, value)
        break


def _set_windows_app_id() -> None:
    if sys.platform != "win32":
        return

    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("LoLScout.MMRLoL")
    except Exception:
        return


def _load_app_icon() -> QIcon:
    project_root = Path(__file__).resolve().parents[2]
    bundle_root = Path(getattr(sys, "_MEIPASS", project_root))
    candidate_paths = (
        bundle_root / "src" / "lolscout" / "ui" / "img" / "mmr-logo-app.png",
        bundle_root / "src" / "lolscout" / "ui" / "img" / "mmr-logo.png",
        bundle_root / "ui" / "img" / "mmr-logo-app.png",
        bundle_root / "ui" / "img" / "mmr-logo.png",
        project_root / "src" / "lolscout" / "ui" / "img" / "mmr-logo-app.png",
        project_root / "src" / "lolscout" / "ui" / "img" / "mmr-logo.png",
        Path.cwd() / "src" / "lolscout" / "ui" / "img" / "mmr-logo-app.png",
        Path.cwd() / "src" / "lolscout" / "ui" / "img" / "mmr-logo.png",
        bundle_root / "src" / "lolscout" / "ui" / "img" / "mmr-logo.ico",
        bundle_root / "ui" / "img" / "mmr-logo.ico",
        project_root / "src" / "lolscout" / "ui" / "img" / "mmr-logo.ico",
        Path.cwd() / "src" / "lolscout" / "ui" / "img" / "mmr-logo.ico",
    )
    for icon_path in candidate_paths:
        if icon_path.exists():
            pixmap = QPixmap()
            if pixmap.load(str(icon_path)):
                icon = QIcon()
                icon.addPixmap(pixmap)
                return icon
    return QIcon()


def main() -> int:
    _load_dotenv()
    _set_windows_app_id()

    from .ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("LoL Scout")
    app.setOrganizationName("LoLScout")
    app_icon = _load_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)
    window = MainWindow()
    if not app_icon.isNull():
        window.setWindowIcon(app_icon)
    window.show()
    return app.exec()
