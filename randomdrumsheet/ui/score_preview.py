from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QFrame, QScrollArea, QWidget

from ..notation.engraver import Engraver
from . import style


class ScorePreview(QWidget):

    def __init__(self, score, staff_space: float = 11.0, parent=None):
        super().__init__(parent)
        self.score = score
        self.engraver = Engraver(staff_space)
        self._layout = None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout = self.engraver.layout(self.score, max(self.width(), 300))
        self.setMinimumHeight(int(self._layout.height))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(style.SCORE_BG))
        if self._layout is None:
            self._layout = self.engraver.layout(self.score, max(self.width(), 300))
        self.engraver.paint(painter, self.score, self._layout)


def preview_area(score, staff_space: float = 11.0) -> QScrollArea:
    area = QScrollArea()
    area.setWidget(ScorePreview(score, staff_space))
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.StyledPanel)
    area.setStyleSheet(f"QScrollArea {{ background: {style.SCORE_BG}; }}")
    return area
