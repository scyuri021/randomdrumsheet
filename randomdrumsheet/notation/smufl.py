from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QFont, QFontMetricsF, QPainter

FONT_FAMILY = "Bravura"

NOTE_WHOLE = ""
NOTE_HALF_UP = ""
NOTE_QUARTER_UP = ""
NOTE_8TH_UP = ""
NOTE_16TH_UP = ""
NOTE_32ND_UP = ""
NOTE_64TH_UP = ""
AUGMENTATION_DOT = ""
NOTEHEAD_BLACK = ""
NOTEHEAD_X = ""

NOTEHEADS = {
    "normal": ("", "", ""),
    "x": ("", "", ""),
    "circle_x": ("", "", ""),
    "diamond": ("", "", ""),
}

FLAGS = {1: ("", ""), 2: ("", ""),
         3: ("", ""), 4: ("", "")}

RESTS = {1: "", 2: "", 4: "", 8: "",
         16: "", 32: "", 64: ""}

CLEF_PERCUSSION = ""
TIME_SIG_DIGITS = [chr(0xE080 + d) for d in range(10)]
TUPLET_DIGITS = [chr(0xE880 + d) for d in range(10)]
TREMOLO_STROKES = {1: "", 2: "", 3: "", 4: ""}
BUZZ_ROLL = ""

ARTICULATIONS = {
    "staccato": ("", ""),
    "tenuto": ("", ""),
    "accent": ("", ""),
    "marcato": ("", ""),
    "hihat_open": ("", ""),
    "hihat_closed": ("", ""),
}
ARTICULATION_ORDER = list(ARTICULATIONS)

REST_WHOLE = ""
REST_QUARTER = ""

ART_ACCENT_ABOVE = ""
ART_STACCATO_ABOVE = ""
ART_TENUTO_ABOVE = ""
ART_MARCATO_ABOVE = ""

STAFF_LINE_THICKNESS = 0.13
THIN_BARLINE_THICKNESS = 0.16
STEM_THICKNESS = 0.12
BEAM_THICKNESS = 0.5


def music_font(staff_space: float) -> QFont:
    font = QFont(FONT_FAMILY)
    font.setPixelSize(max(1, round(staff_space * 4)))
    font.setHintingPreference(QFont.PreferNoHinting)
    return font


def glyph_bounds(glyph: str, font: QFont) -> QRectF:
    return QFontMetricsF(font).tightBoundingRect(glyph)


def glyph_advance(glyph: str, font: QFont) -> float:
    return QFontMetricsF(font).horizontalAdvance(glyph)


def draw_glyph(painter: QPainter, glyph: str, origin: QPointF, font: QFont):
    painter.setFont(font)
    painter.drawText(origin, glyph)


def draw_glyph_centered(painter: QPainter, glyph: str, center: QPointF, font: QFont):
    bounds = glyph_bounds(glyph, font)
    draw_glyph(painter, glyph,
               QPointF(center.x() - bounds.center().x(),
                       center.y() - bounds.center().y()),
               font)
