import math
from typing import Callable, Optional

from PySide6.QtCore import QEasingCurve, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton

from . import style

PictogramFn = Callable[[QPainter, QRectF, QColor], None]


def _lerp_color(a: QColor, b: QColor, t: float) -> QColor:
    return QColor(
        round(a.red() + (b.red() - a.red()) * t),
        round(a.green() + (b.green() - a.green()) * t),
        round(a.blue() + (b.blue() - a.blue()) * t),
    )


class SquareHoverButton(QAbstractButton):

    ICON_RATIO = 0.36

    def __init__(self, text: str, pictogram: Optional[PictogramFn] = None,
                 size: int = 200, hover_scale: float = 1.07, parent=None):
        super().__init__(parent)
        self.setText(text)
        self._pictogram = pictogram
        self._size = size
        self._hover_scale = hover_scale
        self._progress = 0.0

        self._bg = QColor(style.BUTTON_BG_COLOR)
        self._hover_bg = QColor(style.BUTTON_HOVER_BG_COLOR)
        self._border = QColor(style.BUTTON_BORDER_COLOR)
        self._text_color = QColor(style.BUTTON_TEXT_COLOR)
        self._icon_color = QColor(style.ICON_COLOR)
        self._icon_hover_color = QColor(style.ICON_HOVER_COLOR)

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_progress)

        outer = math.ceil(size * hover_scale) + 4
        self.setFixedSize(outer, outer)
        self.setCursor(Qt.PointingHandCursor)

        font = QFont(style.BUTTON_FONT_FAMILY, 15, QFont.Bold)
        font.setHintingPreference(QFont.PreferNoHinting)
        self.setFont(font)

    def _on_progress(self, value):
        self._progress = float(value)
        self.update()

    def _animate_to(self, target: float):
        self._anim.stop()
        self._anim.setStartValue(self._progress)
        self._anim.setEndValue(target)
        self._anim.start()

    def enterEvent(self, event):
        self._animate_to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_to(0.0)
        super().leaveEvent(event)

    def paintEvent(self, event):
        t = self._progress
        scale = 1 + (self._hover_scale - 1) * t
        half = self._size / 2

        bg = _lerp_color(self._bg, self._hover_bg, t)
        if self.isDown():
            bg = bg.darker(108)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        painter.translate(self.width() / 2, self.height() / 2)
        painter.scale(scale, scale)

        painter.setPen(QPen(self._border, 2))
        painter.setBrush(bg)
        painter.drawRoundedRect(QRectF(-half + 1, -half + 1,
                                       self._size - 2, self._size - 2), 6, 6)

        icon_side = self._size * self.ICON_RATIO
        spacing = self._size * 0.09
        text_h = self._size * 0.16
        content_top = -(icon_side + spacing + text_h) / 2

        if self._pictogram is not None:
            icon_rect = QRectF(-icon_side / 2, content_top, icon_side, icon_side)
            icon_color = _lerp_color(self._icon_color, self._icon_hover_color, t)
            self._pictogram(painter, icon_rect, icon_color)

        text_rect = QRectF(-half + 10, content_top + icon_side + spacing,
                           self._size - 20, text_h)
        painter.setPen(self._text_color)
        painter.setFont(self.font())
        painter.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, self.text())
