from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter


def _remove_light_background(image: QImage, threshold: int = 244) -> QImage:
    converted = image.convertToFormat(QImage.Format_ARGB32)
    for y in range(converted.height()):
        for x in range(converted.width()):
            color = converted.pixelColor(x, y)
            if color.red() >= threshold and color.green() >= threshold and color.blue() >= threshold:
                color.setAlpha(0)
                converted.setPixelColor(x, y, color)
    return converted


def _crop_transparent_margins(image: QImage) -> QImage:
    width = image.width()
    height = image.height()
    left = width
    top = height
    right = -1
    bottom = -1

    for y in range(height):
        for x in range(width):
            if image.pixelColor(x, y).alpha() <= 0:
                continue
            if x < left:
                left = x
            if y < top:
                top = y
            if x > right:
                right = x
            if y > bottom:
                bottom = y

    if right < left or bottom < top:
        return image

    return image.copy(left, top, (right - left) + 1, (bottom - top) + 1)


def _build_square_canvas(image: QImage, size: int = 256) -> QImage:
    scaled = image.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    canvas = QImage(size, size, QImage.Format_ARGB32)
    canvas.fill(Qt.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    painter.drawImage((size - scaled.width()) // 2, (size - scaled.height()) // 2, scaled)
    painter.end()
    return canvas


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    source = project_root / "src" / "lolscout" / "ui" / "img" / "mmr-logo.png"
    clean_png = project_root / "src" / "lolscout" / "ui" / "img" / "mmr-logo-app.png"
    target = project_root / "src" / "lolscout" / "ui" / "img" / "mmr-logo.ico"

    image = QImage(str(source))
    if image.isNull():
        raise RuntimeError(f"No se pudo cargar el logo PNG: {source}")

    processed = _build_square_canvas(_crop_transparent_margins(_remove_light_background(image)), size=256)
    if not processed.save(str(clean_png)):
        raise RuntimeError(f"No se pudo generar el PNG de app: {clean_png}")

    if not processed.save(str(target)):
        raise RuntimeError(f"No se pudo generar el icono ICO: {target}")

    print(f"Assets generados: {clean_png} y {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
