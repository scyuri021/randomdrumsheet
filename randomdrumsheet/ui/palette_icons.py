from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF

from ..notation import smufl
from ..notation.engraver import draw_grace
from ..notation.model import TREMOLO_STROKES
from . import style

NOTE_SP = 7.5
SIGN_SP = 8.0
ART_SP = 13.0
NOTEHEAD_SP = 15.0


def note(glyph: str):
    def paint(painter: QPainter, rect: QRectF, color: QColor):
        font = smufl.music_font(NOTE_SP)
        bounds = smufl.glyph_bounds(glyph, font)
        painter.setPen(color)
        smufl.draw_glyph(painter, glyph,
                         QPointF(rect.center().x() - bounds.center().x(),
                                 rect.center().y() + 1.6 * NOTE_SP),
                         font)
    return paint


def sign(glyph: str, staff_space: float = SIGN_SP):
    def paint(painter: QPainter, rect: QRectF, color: QColor):
        painter.setPen(color)
        smufl.draw_glyph_centered(painter, glyph, rect.center(),
                                  smufl.music_font(staff_space))
    return paint


def dotted_note(painter: QPainter, rect: QRectF, color: QColor):
    sp = NOTE_SP
    font = smufl.music_font(sp)
    note_w = smufl.glyph_advance(smufl.NOTE_QUARTER_UP, font)
    gap = 0.3 * sp
    total_w = note_w + gap + smufl.glyph_bounds(smufl.AUGMENTATION_DOT, font).width()
    x = rect.center().x() - total_w / 2
    baseline = rect.center().y() + 1.6 * sp

    painter.setPen(color)
    smufl.draw_glyph(painter, smufl.NOTE_QUARTER_UP, QPointF(x, baseline), font)
    smufl.draw_glyph(painter, smufl.AUGMENTATION_DOT,
                     QPointF(x + note_w + gap, baseline), font)


def tuplet(count: int):
    def paint(painter: QPainter, rect: QRectF, color: QColor):
        sp = 5.0 if count <= 3 else 3.6
        font = smufl.music_font(sp)
        head = smufl.glyph_bounds(smufl.NOTEHEAD_BLACK, font)
        step = (2.3 if count <= 3 else 1.75) * sp
        stem_w = smufl.STEM_THICKNESS * sp * 1.4
        stem_h = 3.0 * sp if count <= 3 else 3.6 * sp
        beams = 1 if count <= 3 else 2
        total_w = (count - 1) * step + head.width()
        left = rect.center().x() - total_w / 2
        baseline = rect.center().y() + (2.1 if count <= 3 else 2.6) * sp
        beam_top = baseline - stem_h

        painter.setPen(color)
        for i in range(count):
            smufl.draw_glyph(painter, smufl.NOTEHEAD_BLACK,
                             QPointF(left + i * step - head.left(), baseline), font)

        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        stem_xs = [left + i * step + head.width() - stem_w for i in range(count)]
        for x in stem_xs:
            painter.drawRect(QRectF(x, beam_top, stem_w, stem_h - 0.15 * sp))
        for b in range(beams):
            painter.drawRect(QRectF(stem_xs[0], beam_top + b * 0.75 * sp,
                                    stem_xs[-1] + stem_w - stem_xs[0],
                                    smufl.BEAM_THICKNESS * sp))

        painter.setPen(color)
        beam_mid = (stem_xs[0] + stem_xs[-1] + stem_w) / 2
        digits = "".join(smufl.TUPLET_DIGITS[int(d)] for d in str(count))
        smufl.draw_glyph_centered(painter, digits, QPointF(beam_mid, beam_top - 5.0),
                                  smufl.music_font(4.5))
    return paint


triplet = tuplet(3)
sextuplet = tuplet(6)


def flip_direction(painter: QPainter, rect: QRectF, color: QColor):
    sp = 6.0
    font = smufl.music_font(sp)
    note_w = smufl.glyph_advance(smufl.NOTE_QUARTER_UP, font)
    arrow_w = 1.3 * sp
    gap = 0.6 * sp
    x = rect.center().x() - (note_w + gap + arrow_w) / 2
    baseline = rect.center().y() + 1.6 * sp

    painter.setPen(color)
    smufl.draw_glyph(painter, smufl.NOTE_QUARTER_UP, QPointF(x, baseline), font)

    ax = x + note_w + gap
    top, bottom = baseline - 2.6 * sp, baseline - 0.2 * sp
    arc = QPainterPath(QPointF(ax, top))
    arc.cubicTo(ax + arrow_w, top, ax + arrow_w, bottom, ax + 0.1 * sp, bottom)
    pen = QPen(color, 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawPath(arc)
    tip = QPointF(ax + 0.1 * sp, bottom)
    painter.drawLine(tip, tip + QPointF(0.55 * sp, -0.5 * sp))
    painter.drawLine(tip, tip + QPointF(0.6 * sp, 0.35 * sp))


def tremolo(kind: str):

    glyph = smufl.BUZZ_ROLL if kind == "buzz" else \
        smufl.TREMOLO_STROKES[TREMOLO_STROKES[kind]]

    def paint(painter: QPainter, rect: QRectF, color: QColor):
        sp = NOTE_SP
        font = smufl.music_font(sp)
        bounds = smufl.glyph_bounds(smufl.NOTE_QUARTER_UP, font)
        origin = QPointF(rect.center().x() - bounds.center().x(),
                         rect.center().y() + 1.6 * sp)
        painter.setPen(color)
        smufl.draw_glyph(painter, smufl.NOTE_QUARTER_UP, origin, font)

        stem_x = origin.x() + bounds.right() - smufl.STEM_THICKNESS * sp / 2
        smufl.draw_glyph_centered(painter, glyph, QPointF(stem_x, origin.y() - 2.1 * sp), font)
    return paint


def grace(kind: str):
    def paint(painter: QPainter, rect: QRectF, color: QColor):
        sp = 6.0
        head = smufl.NOTEHEADS["normal"][2]
        head_w = smufl.glyph_advance(head, smufl.music_font(sp))
        painter.setPen(color)
        draw_grace(painter, rect.center().x() - head_w / 2 - 0.3 * sp,
                   rect.center().y() + 1.6 * sp, kind, head, sp)
    return paint


def _hairpin(painter: QPainter, rect: QRectF, color: QColor, opening_right: bool):
    w, h = 34.0, 12.0
    c = rect.center()
    tip_x = c.x() - w / 2 if opening_right else c.x() + w / 2
    open_x = c.x() + w / 2 if opening_right else c.x() - w / 2
    painter.setPen(QPen(color, 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.setBrush(Qt.NoBrush)
    painter.drawPolyline(QPolygonF([
        QPointF(open_x, c.y() - h / 2),
        QPointF(tip_x, c.y()),
        QPointF(open_x, c.y() + h / 2),
    ]))


def crescendo(painter: QPainter, rect: QRectF, color: QColor):
    _hairpin(painter, rect, color, opening_right=True)


def decrescendo(painter: QPainter, rect: QRectF, color: QColor):
    _hairpin(painter, rect, color, opening_right=False)


HIHAT_MARK_RADIUS = 5.5
HIHAT_MARK_PEN = 2.0


def hihat_open(painter: QPainter, rect: QRectF, color: QColor):
    painter.setPen(QPen(color, HIHAT_MARK_PEN))
    painter.setBrush(Qt.NoBrush)
    painter.drawEllipse(rect.center(), HIHAT_MARK_RADIUS, HIHAT_MARK_RADIUS)


def hihat_closed(painter: QPainter, rect: QRectF, color: QColor):
    c, r = rect.center(), HIHAT_MARK_RADIUS + 0.5
    painter.setPen(QPen(color, HIHAT_MARK_PEN, Qt.SolidLine, Qt.RoundCap))
    painter.drawLine(QPointF(c.x() - r, c.y()), QPointF(c.x() + r, c.y()))
    painter.drawLine(QPointF(c.x(), c.y() - r), QPointF(c.x(), c.y() + r))


def dropdown_arrow(painter: QPainter, rect: QRectF, color: QColor):
    c = rect.center()
    w, h = 8.0, 5.0
    painter.setPen(Qt.NoPen)
    painter.setBrush(color)
    painter.drawPolygon(QPolygonF([
        QPointF(c.x() - w / 2, c.y() - h / 2),
        QPointF(c.x() + w / 2, c.y() - h / 2),
        QPointF(c.x(), c.y() + h / 2),
    ]))


def text_a(painter: QPainter, rect: QRectF, color: QColor):
    font = QFont(style.BUTTON_FONT_FAMILY, 17, QFont.Bold)
    painter.setPen(color)
    painter.setFont(font)
    painter.drawText(rect, Qt.AlignCenter, "A")


def pointer(painter: QPainter, rect: QRectF, color: QColor):
    c = rect.center()
    pts = [(-4.5, -10), (-4.5, 7), (-0.6, 3.4), (2.3, 9.6), (5.0, 8.4), (2.1, 2.3), (7.2, 2.3)]
    painter.setPen(QPen(color, 1.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.setBrush(color)
    painter.drawPolygon(QPolygonF([QPointF(c.x() + x - 1, c.y() + y) for x, y in pts]))


def plus(painter: QPainter, rect: QRectF, color: QColor):
    half = 7.0
    c = rect.center()
    painter.setPen(QPen(color, 2.4, Qt.SolidLine, Qt.RoundCap))
    painter.drawLine(QPointF(c.x() - half, c.y()), QPointF(c.x() + half, c.y()))
    painter.drawLine(QPointF(c.x(), c.y() - half), QPointF(c.x(), c.y() + half))
