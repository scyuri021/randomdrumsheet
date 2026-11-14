from typing import Optional

from PySide6.QtCore import QMarginsF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPageSize, QPainter, QPdfWriter

from .engraver import Engraver
from .model import Score

PAGE_W, PAGE_H = 595.0, 842.0
MARGIN = 42.0
TITLE_H = 54.0
FOOTER_H = 22.0
STAFF_SPACE = 4.8 
TITLE_FONT = "NanumSquare"


class SheetEngraver(Engraver):
    MARGIN_X = 0.0
    MARGIN_TOP = 0.0
    STAFF_ABOVE = 9.0
    STAFF_BELOW = 9.5


class SheetRenderer:
    def __init__(self, score: Score, title: str = "", per_line: Optional[int] = 4,
                 staff_space: float = STAFF_SPACE):
        self.score = score
        self.title = title.strip()
        self.engraver = SheetEngraver(staff_space)
        self.content_w = PAGE_W - 2 * MARGIN
        self.layout = self.engraver.layout(score, self.content_w, per_line, numbers=True)
        self.pages = self._paginate()

    def _paginate(self) -> list:
        system_h = self.engraver.system_height()
        pages, current = [], []
        room = PAGE_H - 2 * MARGIN - FOOTER_H - (TITLE_H if self.title else 0)
        for system in self.layout.systems:
            if current and room < system_h:
                pages.append(current)
                current = []
                room = PAGE_H - 2 * MARGIN - FOOTER_H
            current.append(system.index)
            room -= system_h
        if current:
            pages.append(current)
        return pages

    @property
    def page_count(self) -> int:
        return len(self.pages)

    def render(self, painter: QPainter, page: int, scale: float):
        sp = self.engraver.sp
        painter.save()
        painter.scale(scale, scale)
        painter.fillRect(QRectF(0, 0, PAGE_W, PAGE_H), QColor("#ffffff"))
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        top = MARGIN
        if page == 0 and self.title:
            font = QFont(TITLE_FONT)
            font.setPixelSize(22)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QColor("#1c1c1c"))
            painter.drawText(QRectF(MARGIN, MARGIN, self.content_w, TITLE_H - 14),
                             Qt.AlignHCenter | Qt.AlignVCenter, self.title)
            top += TITLE_H

        systems = [self.layout.systems[i] for i in self.pages[page]]
        band_top = systems[0].top - self.engraver.STAFF_ABOVE * sp
        band_bottom = systems[-1].top + (4 + self.engraver.STAFF_BELOW) * sp
        painter.save()
        painter.translate(MARGIN, top - band_top)
        painter.setClipRect(QRectF(-MARGIN, band_top, PAGE_W, band_bottom - band_top))
        self.engraver.paint(painter, self.score, self.layout)
        painter.restore()

        if self.page_count > 1:
            font = QFont(TITLE_FONT)
            font.setPixelSize(9)
            painter.setFont(font)
            painter.setPen(QColor("#555555"))
            painter.drawText(QRectF(0, PAGE_H - MARGIN, PAGE_W, FOOTER_H),
                             Qt.AlignHCenter | Qt.AlignVCenter,
                             f"{page + 1} / {self.page_count}")
        painter.restore()

    def page_image(self, page: int, scale: float, ratio: float = 1.0) -> QImage:
        image = QImage(int(PAGE_W * scale * ratio), int(PAGE_H * scale * ratio),
                       QImage.Format_RGB32)
        image.setDevicePixelRatio(ratio)
        image.fill(QColor("#ffffff"))
        painter = QPainter(image)
        self.render(painter, page, scale)
        painter.end()
        return image

    def save_pdf(self, path: str):
        writer = QPdfWriter(path)
        writer.setPageSize(QPageSize(QPageSize.A4))
        writer.setPageMargins(QMarginsF(0, 0, 0, 0))
        writer.setResolution(300)
        writer.setTitle(self.title or "RandomDrumSheet")
        writer.setCreator("RandomDrumSheet")
        painter = QPainter(writer)
        scale = writer.resolution() / 72.0
        for page in range(self.page_count):
            if page:
                writer.newPage()
            self.render(painter, page, scale)
        painter.end()
