from __future__ import annotations

import os
import sys
from pathlib import Path

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


def main() -> int:
    _load_dotenv()

    from .ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("LoL Scout")
    app.setOrganizationName("LoLScout")
    window = MainWindow()
    window.show()
    return app.exec()
