from PySide6.QtCore import QPoint, QRect, QRectF, QSize, QStringListModel, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (QCompleter, QLayout, QLineEdit, QVBoxLayout, QWidget,
                               QWidgetItem)

from . import style

TAG_FONT = QFont(style.BUTTON_FONT_FAMILY, 10)


def clean_tag(text: str) -> str:
    return text.strip().lstrip("#").strip()


class FlowLayout(QLayout):

    def __init__(self, parent=None, spacing=6):
        super().__init__(parent)
        self._items = []
        self._spacing = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def insert_widget(self, index: int, widget: QWidget):
        self.addChildWidget(widget)
        self._items.insert(index, QWidgetItem(widget))
        self.invalidate()

    def index_of(self, widget) -> int:
        for i, item in enumerate(self._items):
            if item.widget() is widget:
                return i
        return -1

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._arrange(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._arrange(rect, apply=True)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size

    def _arrange(self, rect, apply):
        m = self.contentsMargins()
        outer_top = rect.y()
        rect = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, line_h = rect.x(), rect.y(), 0
        for item in self._items:
            if item.isEmpty():
                continue
            hint = item.sizeHint()
            if x + hint.width() > rect.right() and line_h > 0:
                x, y = rect.x(), y + line_h + self._spacing
                line_h = 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self._spacing
            line_h = max(line_h, hint.height())
        return y + line_h - outer_top + m.bottom()


class TagChip(QWidget):
    removed = Signal(object)
    edit_requested = Signal(object)

    PAD = 8

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.text = text
        self._hover = False
        self.setFont(TAG_FONT)
        self.setMouseTracking(True)
        self.setToolTip("더블클릭하여 수정")

    def set_text(self, text: str):
        self.text = text
        self.updateGeometry()
        self.update()

    def _prefix_rect(self) -> QRectF:
        h = self.height()
        return QRectF(self.PAD - 2, 0, h - 6, h)

    def sizeHint(self):
        fm = QFontMetrics(self.font())
        h = fm.height() + 12
        return QSize(self.PAD * 2 + (h - 6) + 2 + fm.horizontalAdvance(self.text), h)

    def enterEvent(self, event):
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.unsetCursor()
        self.update()

    def mouseMoveEvent(self, event):
        if self._prefix_rect().contains(event.position()):
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.unsetCursor()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._prefix_rect().contains(event.position()):
            self.removed.emit(self)

    def mouseDoubleClickEvent(self, event):
        if not self._prefix_rect().contains(event.position()):
            self.edit_requested.emit(self)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColor("#b0b0b4"), 1))
        p.setBrush(QColor("#ffffff") if self._hover else QColor(style.PALETTE_GROUP_BG))
        p.drawRoundedRect(r, 6, 6)

        prefix = self._prefix_rect()
        ink = QColor(style.PALETTE_GLYPH_COLOR)
        if self._hover:
            c, rad = prefix.center(), min(prefix.width(), prefix.height()) * 0.36
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#7c7c7c"))
            p.drawEllipse(c, rad, rad)
            p.setPen(QPen(QColor("#ffffff"), 1.6, Qt.SolidLine, Qt.RoundCap))
            d = rad * 0.45
            p.drawLine(c.x() - d, c.y() - d, c.x() + d, c.y() + d)
            p.drawLine(c.x() - d, c.y() + d, c.x() + d, c.y() - d)
        else:
            p.setPen(ink)
            p.drawText(prefix, Qt.AlignCenter, "#")
        p.setPen(ink)
        text_rect = QRectF(prefix.right() + 2, 0, self.width() - prefix.right() - 2, self.height())
        p.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text)


class TagEditor(QWidget):
    changed = Signal()

    def __init__(self, suggestions=(), tags=(), parent=None):
        super().__init__(parent)
        self.input = QLineEdit()
        self.input.setFont(TAG_FONT)
        self.input.setPlaceholderText("태그 입력 후 Enter")
        self.input.returnPressed.connect(self._add_from_input)

        self._model = QStringListModel(sorted(set(suggestions)))
        self.completer = QCompleter(self._model, self)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchStartsWith)
        self.completer.activated.connect(self._completion_chosen)
        self.input.setCompleter(self.completer)

        self.chips_box = QWidget()
        self.flow = FlowLayout(self.chips_box)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.input)
        layout.addWidget(self.chips_box)
        for t in tags:
            self.add_tag(t)

    def tags(self) -> list:
        result = []
        for i in range(self.flow.count()):
            w = self.flow.itemAt(i).widget()
            if isinstance(w, TagChip):
                result.append(w.text)
        return result

    def add_tag(self, text: str) -> bool:
        tag = clean_tag(text)
        if not tag or tag in self.tags():
            return False
        chip = TagChip(tag)
        chip.removed.connect(self._remove_chip)
        chip.edit_requested.connect(self._edit_chip)
        self.flow.addWidget(chip)
        self._remember(tag)
        self.changed.emit()
        return True

    def _remember(self, tag: str):
        items = self._model.stringList()
        if tag not in items:
            self._model.setStringList(sorted(items + [tag]))

    def _add_from_input(self):
        self.add_tag(self.input.text())
        self.input.clear()

    def _completion_chosen(self, text: str):
        QTimer.singleShot(0, lambda: (self.add_tag(text), self.input.clear()))

    def _remove_chip(self, chip: TagChip):
        index = self.flow.index_of(chip)
        if index >= 0:
            self.flow.takeAt(index)
        chip.deleteLater()
        self.changed.emit()

    def _edit_chip(self, chip: TagChip):
        index = self.flow.index_of(chip)
        editor = QLineEdit(chip.text)
        editor.setFont(TAG_FONT)
        editor.setFixedWidth(max(120, chip.width() + 40))
        editor.setCompleter(self.completer)
        self.flow.takeAt(index)
        chip.hide()
        self.flow.insert_widget(index, editor)
        editor.setFocus()
        editor.selectAll()
        done = {"closed": False}

        def finish(commit: bool):
            if done["closed"]:
                return
            done["closed"] = True
            new = clean_tag(editor.text())
            pos = self.flow.index_of(editor)
            self.flow.takeAt(pos)
            editor.deleteLater()
            if commit and (not new or new in self.tags()):
                chip.deleteLater()
            else:
                if commit:
                    chip.set_text(new)
                    self._remember(new)
                self.flow.insert_widget(pos, chip)
                chip.show()
            self.changed.emit()

        editor.returnPressed.connect(lambda: finish(True))
        editor.editingFinished.connect(lambda: finish(True))
        editor.installEventFilter(self)
        editor._finish = finish

    def eventFilter(self, obj, event):
        if event.type() == event.Type.KeyPress and event.key() == Qt.Key_Escape \
                and hasattr(obj, "_finish"):
            obj._finish(False)
            return True
        return super().eventFilter(obj, event)
