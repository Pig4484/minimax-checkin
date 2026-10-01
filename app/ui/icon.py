"""介面圖示（以程式繪製，免外部資源檔）。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)


def app_pixmap(size: int = 256) -> QPixmap:
    """圓角漸層底 + 白色勾勾的 App 圖示。"""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0.0, QColor("#3b82f6"))
    gradient.setColorAt(1.0, QColor("#1d4ed8"))
    path = QPainterPath()
    radius = size * 0.24
    path.addRoundedRect(QRectF(size * 0.05, size * 0.05, size * 0.9, size * 0.9), radius, radius)
    painter.fillPath(path, gradient)

    pen = QPen(QColor(255, 255, 255))
    pen.setWidthF(size * 0.085)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.drawPolyline(
        QPolygonF(
            [
                QPointF(size * 0.27, size * 0.52),
                QPointF(size * 0.44, size * 0.69),
                QPointF(size * 0.74, size * 0.33),
            ]
        )
    )
    painter.end()
    return pixmap


def app_icon() -> QIcon:
    """優先用 assets/app.ico（多尺寸、工作列更清晰），否則即時繪製。"""
    ico = Path(__file__).resolve().parent.parent.parent / "assets" / "app.ico"
    if ico.exists():
        icon = QIcon(str(ico))
        if not icon.isNull():
            return icon
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(app_pixmap(size))
    return icon
