from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPolygonF


def _begin(painter: QPainter, color: QColor):
    painter.save()
    painter.setPen(Qt.NoPen)
    painter.setBrush(color)


def draw_folder(painter: QPainter, rect: QRectF, color: QColor):
    _begin(painter, color)
    w, h = rect.width(), rect.height()
    left, top = rect.left(), rect.top() + h * 0.12
    body_h = h * 0.70
    radius = w * 0.07

    tab = QPainterPath()
    tab.addRoundedRect(QRectF(left, top, w * 0.42, h * 0.22), radius, radius)
    body = QPainterPath()
    body.addRoundedRect(QRectF(left, top + h * 0.1, w, body_h), radius, radius)
    painter.drawPath(tab.united(body))
    painter.restore()


def draw_pencil(painter: QPainter, rect: QRectF, color: QColor):
    _begin(painter, color)
    length = rect.width() * 1.28
    thick = rect.width() * 0.26
    gap = rect.width() * 0.045
    tip_len = length * 0.24
    eraser_len = length * 0.15
    half = length / 2

    painter.translate(rect.center())
    painter.rotate(-45)

    tip = QPolygonF([
        QPointF(-half, 0),
        QPointF(-half + tip_len, -thick / 2),
        QPointF(-half + tip_len, thick / 2),
    ])
    painter.drawPolygon(tip)

    body_left = -half + tip_len + gap
    body_right = half - eraser_len - gap
    painter.drawRect(QRectF(body_left, -thick / 2, body_right - body_left, thick))

    eraser = QPainterPath()
    eraser.addRoundedRect(QRectF(half - eraser_len, -thick / 2, eraser_len, thick),
                          thick * 0.3, thick * 0.3)
    painter.drawPath(eraser)
    painter.restore()


def draw_eighth_note(painter: QPainter, rect: QRectF, color: QColor):
    _begin(painter, color)
    w, h = rect.width(), rect.height()
    head_rx, head_ry = w * 0.2, w * 0.14
    stem_w = w * 0.075
    flag_w = w * 0.3

    total_w = head_rx * 2 + flag_w - stem_w
    head_cx = rect.center().x() - total_w / 2 + head_rx
    head_cy = rect.bottom() - head_ry * 1.3

    painter.save()
    painter.translate(head_cx, head_cy)
    painter.rotate(-22)
    painter.drawEllipse(QPointF(0, 0), head_rx, head_ry)
    painter.restore()

    stem_right = head_cx + head_rx * 0.95
    top = rect.top()
    painter.drawRect(QRectF(stem_right - stem_w, top, stem_w, head_cy - top))

    flag = QPainterPath(QPointF(stem_right - 0.5, top))
    flag.cubicTo(stem_right + flag_w * 0.05, top + h * 0.16,
                 stem_right + flag_w * 1.15, top + h * 0.22,
                 stem_right + flag_w * 0.8, top + h * 0.56)
    flag.cubicTo(stem_right + flag_w * 0.9, top + h * 0.36,
                 stem_right + flag_w * 0.4, top + h * 0.3,
                 stem_right - 0.5, top + h * 0.27)
    flag.closeSubpath()
    painter.drawPath(flag)
    painter.restore()
