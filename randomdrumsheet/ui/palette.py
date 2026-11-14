from typing import Callable, Optional

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QIntValidator, QPainter, QPixmap
from PySide6.QtWidgets import (QAbstractButton, QFrame, QGridLayout, QHBoxLayout,
                               QLineEdit, QMenu, QPushButton, QVBoxLayout, QWidget)

from . import style
from .palette_icons import dropdown_arrow

IconPainter = Callable[[QPainter, QRectF, QColor], None]


class PaletteButton(QAbstractButton):

    def __init__(self, icon: IconPainter, tooltip: str, width: int = 46,
                 join: Optional[str] = None, parent=None):
        super().__init__(parent)
        self._icon = icon
        self._join = join
        self.setToolTip(tooltip)
        self.setFixedSize(width, 48)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover)
        self.setFocusPolicy(Qt.NoFocus)

    def set_icon(self, icon: IconPainter, tooltip: Optional[str] = None):
        self._icon = icon
        if tooltip is not None:
            self.setToolTip(tooltip)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0 if self._join == "left" else 2, 2,
                                            0 if self._join == "right" else -2, -2)

        if self.isDown() or self.isChecked():
            bg = QColor(style.PALETTE_ACTIVE_BG)
        elif self.underMouse():
            bg = QColor(style.PALETTE_HOVER_BG)
        else:
            bg = None
        if bg is not None:
            painter.setPen(Qt.NoPen)
            painter.setBrush(bg)
            painter.drawRoundedRect(rect, 5, 5)
            half = rect.width() / 2
            if self._join == "right":
                painter.drawRect(rect.adjusted(half, 0, 0, 0))
            elif self._join == "left":
                painter.drawRect(rect.adjusted(0, 0, -half, 0))

        self._icon(painter, rect, QColor(style.PALETTE_GLYPH_COLOR))


def icon_pixmap(icon: IconPainter, size: int = 36) -> QIcon:
    ratio = 2
    pixmap = QPixmap(size * ratio, size * ratio)
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    icon(painter, QRectF(0, 0, size, size), QColor(style.PALETTE_GLYPH_COLOR))
    painter.end()
    return QIcon(pixmap)


class SplitPaletteButton(QWidget):
    triggered = Signal()
    chosen = Signal(str)

    def __init__(self, icon: IconPainter, tooltip: str, menu_tooltip: str, parent=None):
        super().__init__(parent)
        self.button = PaletteButton(icon, tooltip, join="right")
        self.menu_button = PaletteButton(dropdown_arrow, menu_tooltip, width=20, join="left")
        self._items = {}
        self._menu = QMenu(self)
        self._menu.setStyleSheet("QMenu::item { padding: 6px 24px 6px 8px; }")
        self._menu.setFont(QFont(style.BUTTON_FONT_FAMILY, 10))
        self.button.clicked.connect(self.triggered)
        self.menu_button.clicked.connect(self._show_menu)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.button)
        layout.addWidget(self.menu_button)

    def set_items(self, items):
        self._menu.clear()
        self._items = {}
        for key, label, icon in items:
            self._items[key] = (label, icon)
            action = self._menu.addAction(icon_pixmap(icon), label)
            action.triggered.connect(lambda _=False, k=key: self._choose(k))

    def show_item(self, key: str):
        label, icon = self._items[key]
        self.button.set_icon(icon, label)

    def _choose(self, key: str):
        self.show_item(key)
        self.chosen.emit(key)

    def _show_menu(self):
        self._menu.exec(self.mapToGlobal(QPoint(0, self.height())))


class PaletteGroup(QFrame):

    def __init__(self, buttons, parent=None):
        super().__init__(parent)
        self.setObjectName("paletteGroup")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)
        for button in buttons:
            layout.addWidget(button)


class PaletteSeparator(QFrame):

    def __init__(self, height: Optional[int] = 44, width: int = 2, parent=None):
        super().__init__(parent)
        self.setObjectName("paletteSeparator")
        self.setFixedWidth(width)
        if height is not None:
            self.setFixedHeight(height)


class DrumInputButton(QPushButton):

    def __init__(self, name: str, parent=None):
        super().__init__(name, parent)
        self.setObjectName("drumButton")
        self.setFixedSize(88, 48)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFont(QFont(style.BUTTON_FONT_FAMILY, 11, QFont.Bold))


class DrumInputPanel(QFrame):

    COLUMNS = 5

    def __init__(self, names, parent=None):
        super().__init__(parent)
        self.setObjectName("paletteGroup")
        self.buttons = {name: DrumInputButton(name) for name in names}

        layout = QGridLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setHorizontalSpacing(4)
        layout.setVerticalSpacing(12)
        for i, button in enumerate(self.buttons.values()):
            layout.addWidget(button, i // self.COLUMNS, i % self.COLUMNS)


class TimeSigField(QLineEdit):

    def __init__(self, value: int, parent=None):
        super().__init__(str(value), parent)
        self.setObjectName("timeSigField")
        self._last_valid = str(value)
        self.setValidator(QIntValidator(1, 99, self))
        self.setMaxLength(2)
        self.setAlignment(Qt.AlignCenter)
        self.setFrame(False)
        self.setFont(QFont(style.BUTTON_FONT_FAMILY, 20, QFont.Bold))
        self.setFixedHeight(42)
        self.setCursor(Qt.IBeamCursor)
        self.textChanged.connect(self._remember_valid)
        self.returnPressed.connect(self.clearFocus)

    def value(self) -> int:
        return int(self._last_valid)

    def set_value(self, value: int):
        self._last_valid = str(value)
        self.setText(str(value))

    def _remember_valid(self, text):
        if self.hasAcceptableInput():
            self._last_valid = text

    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)

    def focusOutEvent(self, event):
        if not self.hasAcceptableInput():
            self.setText(self._last_valid)
        super().focusOutEvent(event)


class TimeSignatureBox(QFrame):

    edited = Signal(int, int)

    def __init__(self, numerator: int = 4, denominator: int = 4, parent=None):
        super().__init__(parent)
        self.setObjectName("timeSigBox")
        self.setFixedWidth(68)

        self.numerator = TimeSigField(numerator)
        self.denominator = TimeSigField(denominator)
        self.numerator.setToolTip("박자표 분자")
        self.denominator.setToolTip("박자표 분모")
        for field in (self.numerator, self.denominator):
            field.editingFinished.connect(self._emit_edited)

        line = QFrame()
        line.setObjectName("timeSigLine")
        line.setFixedHeight(2)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        layout.addStretch(1)
        layout.addWidget(self.numerator)
        layout.addWidget(line)
        layout.addWidget(self.denominator)
        layout.addStretch(1)

    def set_values(self, numerator: int, denominator: int):
        self.numerator.set_value(numerator)
        self.denominator.set_value(denominator)

    def _emit_edited(self):
        self.edited.emit(self.numerator.value(), self.denominator.value())
