from dataclasses import dataclass, field
from fractions import Fraction
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen

from . import smufl
from .model import Chord, Hairpin, Score, TupletGroup, TREMOLO_STROKES, onsets

F = Fraction

INK = QColor("#1c1c1c")
SELECT_COLORS = (QColor("#1565d8"), QColor("#1f8a3b"))  
CURSOR_FILL = QColor(70, 140, 255, 55)
CURSOR_EDGE = QColor(70, 140, 255, 160)

GRACE_SCALE = 0.62
GRACE_FLAGS = {"acciaccatura": 1, "appoggiatura": 1, "grace16": 2, "grace32": 3}
BEAM_LEVELS = {F(1, 8): 1, F(1, 16): 2, F(1, 32): 3, F(1, 64): 4}


@dataclass
class Hit:
    rect: QRectF
    kind: str
    chord: Optional[Chord] = None
    note: object = None
    hairpin: Optional[Hairpin] = None
    voice: int = 0
    measure: int = -1


@dataclass
class MeasureLayout:
    index: int
    system: int
    x: float
    width: float
    ticks: dict = field(default_factory=dict)
    ts_width: float = 0.0
    repeat_width: float = 0.0


@dataclass
class SystemLayout:
    index: int
    top: float
    x0: float
    x1: float
    content_x: float
    measures: list = field(default_factory=list)


@dataclass
class ChordGeom:
    system: int
    x: float
    head_w: float
    stem_up: bool
    stem_x: float = 0.0
    tip: float = 0.0
    has_stem: bool = True
    beamed: bool = False
    ys: dict = field(default_factory=dict)
    min_y: float = 0.0
    max_y: float = 0.0
    top: float = 0.0


@dataclass
class Shadow:
    measure: int
    tick: Fraction
    line: int
    head: str
    base: Fraction
    dots: int
    voice: int
    rest: bool = False


@dataclass
class Layout:
    systems: list
    measures: list
    width: float
    height: float
    numbers: bool = False


def draw_grace(painter: QPainter, x: float, y: float, kind: str, head: str,
               sp: float, up: bool = True):
    font = smufl.music_font(sp)
    head_w = smufl.glyph_advance(head, font)
    smufl.draw_glyph(painter, head, QPointF(x, y), font)
    stem_w = smufl.STEM_THICKNESS * sp * 1.3
    levels = GRACE_FLAGS[kind]
    length = (3.2 + 0.5 * max(0, levels - 2)) * sp
    stem_x = x + head_w - stem_w if up else x
    tip = y - length if up else y + length
    color = painter.pen().color()
    painter.fillRect(QRectF(stem_x, min(y, tip), stem_w, abs(tip - y) - 0.15 * sp), color)
    flag = smufl.FLAGS[levels][0 if up else 1]
    smufl.draw_glyph(painter, flag, QPointF(stem_x, tip), font)
    if kind == "acciaccatura":
        pen = QPen(color, 0.16 * sp, Qt.SolidLine, Qt.RoundCap)
        painter.save()
        painter.setPen(pen)
        d = 1 if up else -1
        painter.drawLine(QPointF(stem_x - 0.7 * sp, tip + d * 1.9 * sp),
                         QPointF(stem_x + 1.1 * sp, tip + d * 0.6 * sp))
        painter.restore()


class Engraver:
    MARGIN_X = 3.0
    MARGIN_TOP = 3.0
    STAFF_ABOVE = 10.0
    STAFF_BELOW = 12.0
    MEASURE_LEFT_PAD = 1.3
    MEASURE_RIGHT_PAD = 0.7
    EMPTY_MEASURE = 10.0

    def __init__(self, staff_space: float):
        self.sp = staff_space
        self.font = smufl.music_font(staff_space)
        self.head_w = smufl.glyph_advance(smufl.NOTEHEADS["normal"][2], self.font)
        self.text_font = QFont("NanumSquare")
        self.text_font.setPixelSize(round(staff_space * 1.5))
        self.hits: list = []
        self.geoms: dict = {}
        self.positions: dict = {}
        self.beam_groups: list = []
    def _segment_width(self, dur: Fraction) -> float:
        return self.sp * (1.3 + 4.6 * float(dur) ** 0.6)

    def _ts_changes(self, score: Score, mi: int) -> bool:
        return mi == 0 or score.time_sig_of(mi) != score.time_sig_of(mi - 1)

    def _lead(self, score: Score, mi: int) -> tuple:
        sp = self.sp
        ts_w = 0.0
        if self._ts_changes(score, mi):
            n, d = score.time_sig_of(mi)
            ts_w = (1.8 * max(len(str(n)), len(str(d))) + 1.0) * sp
        rep_w = 1.6 * sp if score.measures[mi].repeat_start else 0.0
        return ts_w, rep_w

    def _measure_natural(self, score: Score, mi: int):
        sp = self.sp
        ts_w, rep_w = self._lead(score, mi)
        tail = 1.2 * sp if score.measures[mi].repeat_end else 0.0
        events = [(t, c) for m, _, _, c, t in score.chords() if m == mi]
        ticks = sorted({t for t, _ in events})
        if not ticks:
            return [], self.EMPTY_MEASURE * sp + ts_w + rep_w + tail, ts_w, rep_w
        cap = score.capacity_of(mi)
        x = self.MEASURE_LEFT_PAD * sp + ts_w + rep_w
        result = []
        for i, t in enumerate(ticks):
            here = [c for tt, c in events if tt == t]
            if any(n.grace for c in here for n in c.notes):
                x += 1.6 * sp
            result.append((t, x))
            nxt = ticks[i + 1] if i + 1 < len(ticks) else cap
            x += self._segment_width(nxt - t)
            if any(c.dots for c in here):
                x += 0.5 * sp
        return result, x + self.MEASURE_RIGHT_PAD * sp + tail, ts_w, rep_w

    def _header_width(self) -> float:
        return 3.6 * self.sp

    def system_height(self) -> float:
        return (self.STAFF_ABOVE + 4 + self.STAFF_BELOW) * self.sp

    def layout(self, score: Score, width: float, per_line: Optional[int] = None,
               numbers: bool = False) -> Layout:
        sp = self.sp
        naturals = [self._measure_natural(score, i) for i in range(len(score.measures))]
        x0 = self.MARGIN_X * sp
        x_end = max(width - self.MARGIN_X * sp, x0 + 30 * sp)

        systems, measures = [], []
        i = 0
        while i < len(naturals):
            index = len(systems)
            top = self.MARGIN_TOP * sp + self.STAFF_ABOVE * sp + index * self.system_height()
            content_x = x0 + self._header_width()
            avail = x_end - content_x
            chosen, used = [], 0.0
            if per_line:
                chosen = list(range(i, min(i + per_line, len(naturals))))
                used = sum(naturals[k][1] for k in chosen)
                i += len(chosen)
                factor = avail * len(chosen) / per_line / used if used > 0 else 1.0
            else:
                while i < len(naturals) and (not chosen or used + naturals[i][1] <= avail):
                    chosen.append(i)
                    used += naturals[i][1]
                    i += 1
                last = i >= len(naturals)
                factor = 1.0 if last or used <= 0 else max(avail / used, 1.0)
            system = SystemLayout(index, top, x0, content_x, content_x, chosen)
            x = content_x
            for mi in chosen:
                ticks, w, ts_w, rep_w = naturals[mi]
                lead = ts_w + rep_w
                ml = MeasureLayout(mi, index, x, lead + (w - lead) * factor,
                                   {t: x + lead + (rx - lead) * factor for t, rx in ticks},
                                   ts_w, rep_w)
                measures.append(ml)
                x += ml.width
            system.x1 = x
            systems.append(system)
        height = systems[-1].top + (4 + self.STAFF_BELOW) * sp + self.MARGIN_TOP * sp
        return Layout(systems, measures, width, height, numbers)
    def line_y(self, system: SystemLayout, line: float) -> float:
        return system.top + line * self.sp / 2

    def tick_x(self, layout: Layout, mi: int, tick: Fraction, cap: Fraction) -> float:
        ml = layout.measures[mi]
        if tick in ml.ticks:
            return ml.ticks[tick]
        start = ml.x + ml.ts_width + ml.repeat_width + self.MEASURE_LEFT_PAD * self.sp
        end = ml.x + ml.width - (self.MEASURE_RIGHT_PAD + 0.6) * self.sp - \
            (self.head_w if not ml.ticks else 0)
        if tick >= cap:
            return end
        before = [(t, x) for t, x in ml.ticks.items() if t < tick] or [(F(0), start)]
        after = [(t, x) for t, x in ml.ticks.items() if t > tick] or [(cap, end)]
        t0, x0 = max(before)
        t1, x1 = min(after)
        return x0 + (x1 - x0) * float((tick - t0) / (t1 - t0))

    def hit_test(self, pos: QPointF) -> Optional[Hit]:
        order = {"text": 0, "hairpin": 1, "note": 2, "rest": 3}
        found = [h for h in self.hits if h.rect.contains(pos)]
        return min(found, key=lambda h: order[h.kind]) if found else None

    def staff_position(self, layout: Layout, pos: QPointF) -> Optional[tuple]:
        sp = self.sp
        for ml in layout.measures:
            sysl = layout.systems[ml.system]
            if ml.x <= pos.x() < ml.x + ml.width and \
                    sysl.top - 4 * sp <= pos.y() <= sysl.top + 8 * sp:
                return ml.index, round((pos.y() - sysl.top) / (sp / 2))
        return None

    def nearest_tick(self, layout: Layout, measure: int, ticks, x: float, cap: Fraction):
        return min(ticks, key=lambda t: abs(self.tick_x(layout, measure, t, cap)
                                            + self.head_w / 2 - x))

    def paint(self, painter: QPainter, score: Score, layout: Layout,
              selected: set = frozenset(), cursor: Optional[tuple] = None,
              shadow: Optional["Shadow"] = None):
        self.hits = []
        self.geoms = {}
        self.positions = {}
        self.beam_groups = []
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        if cursor is not None:
            self._paint_cursor(painter, score, layout, cursor)
        for system in layout.systems:
            self._paint_system_frame(painter, score, layout, system)
        for ml in layout.measures:
            self._paint_measure(painter, score, layout, ml, selected)
        self._paint_ties(painter, score, layout)
        self._paint_hairpins(painter, score, layout, selected)
        self._paint_endings(painter, score, layout)
        if shadow is not None:
            self._paint_shadow(painter, score, layout, shadow)

    def _paint_shadow(self, painter, score, layout, s: "Shadow"):
        sp = self.sp
        if s.measure >= len(layout.measures):
            return
        system = layout.systems[layout.measures[s.measure].system]
        x = self.tick_x(layout, s.measure, s.tick, score.capacity_of(s.measure))
        color = QColor(SELECT_COLORS[s.voice])
        color.setAlpha(130)
        painter.setPen(color)
        if s.rest:
            other = score.measures[s.measure].voices[1 - s.voice]
            offset = (-2 * sp if s.voice == 0 else 2 * sp) if other else 0
            glyph = smufl.RESTS[int(1 / s.base)]
            b = smufl.glyph_bounds(glyph, self.font)
            baseline = system.top + (sp if s.base == 1 else 2 * sp) + offset
            smufl.draw_glyph(painter, glyph, QPointF(x + self.head_w / 2 - b.center().x(),
                                                     baseline), self.font)
            return

        y = self.line_y(system, s.line)
        glyph = self._head_glyph(s.head, s.base)
        head_w = smufl.glyph_advance(glyph, self.font)
        self._paint_ledgers(painter, system, x, s.line, color)
        painter.setPen(color)
        smufl.draw_glyph(painter, glyph, QPointF(x, y), self.font)
        up = s.voice == 0
        if s.base < 1:
            stem_w = smufl.STEM_THICKNESS * sp
            levels = BEAM_LEVELS.get(s.base, 0)
            length = (3.5 + {3: 0.5, 4: 1.25}.get(levels, 0)) * sp
            stem_x = x + head_w - stem_w / 2 if up else x + stem_w / 2
            tip = y - length if up else y + length
            painter.fillRect(QRectF(stem_x - stem_w / 2, min(y, tip), stem_w, length), color)
            if levels:
                smufl.draw_glyph(painter, smufl.FLAGS[levels][0 if up else 1],
                                 QPointF(stem_x - stem_w / 2, tip), self.font)
        if s.dots:
            line = s.line + ((-1 if up else 1) if s.line % 2 == 0 else 0)
            smufl.draw_glyph(painter, smufl.AUGMENTATION_DOT,
                             QPointF(x + head_w + 0.35 * sp, self.line_y(system, line)),
                             self.font)

    def _paint_cursor(self, painter, score, layout, cursor):
        mi, tick = cursor
        if mi >= len(layout.measures):
            return
        sp = self.sp
        system = layout.systems[layout.measures[mi].system]
        x = self.tick_x(layout, mi, tick, score.capacity_of(mi))
        rect = QRectF(x - 0.45 * sp, system.top - 1.5 * sp, self.head_w + 0.9 * sp, 7 * sp)
        painter.setPen(QPen(CURSOR_EDGE, 1))
        painter.setBrush(CURSOR_FILL)
        painter.drawRoundedRect(rect, 0.3 * sp, 0.3 * sp)

    def _paint_system_frame(self, painter, score, layout, system):
        sp = self.sp
        painter.setPen(QPen(INK, smufl.STAFF_LINE_THICKNESS * sp, Qt.SolidLine, Qt.FlatCap))
        for i in range(5):
            y = system.top + i * sp
            painter.drawLine(QPointF(system.x0, y), QPointF(system.x1, y))
        thin = smufl.THIN_BARLINE_THICKNESS * sp
        top, bottom = system.top, system.top + 4 * sp
        painter.setPen(QPen(INK, thin, Qt.SolidLine, Qt.FlatCap))
        painter.drawLine(QPointF(system.x0, top), QPointF(system.x0, bottom))
        for pos, mi in enumerate(system.measures):
            ml = layout.measures[mi]
            measure = score.measures[mi]
            x = ml.x + ml.width
            nxt = layout.measures[system.measures[pos + 1]] if pos + 1 < len(system.measures) \
                else None
            replaced = nxt is not None and score.measures[nxt.index].repeat_start \
                and not nxt.ts_width
            if measure.repeat_end:
                self._paint_repeat(painter, system, x, start=False)
            elif mi == len(score.measures) - 1:
                painter.setPen(QPen(INK, thin, Qt.SolidLine, Qt.FlatCap))
                painter.drawLine(QPointF(x - 0.85 * sp, top), QPointF(x - 0.85 * sp, bottom))
                painter.fillRect(QRectF(x - 0.5 * sp, top, 0.5 * sp, 4 * sp), INK)
            elif not replaced:
                painter.setPen(QPen(INK, thin, Qt.SolidLine, Qt.FlatCap))
                painter.drawLine(QPointF(x, top), QPointF(x, bottom))
            if measure.repeat_start:
                inner = pos > 0 and not ml.ts_width
                self._paint_repeat(painter, system,
                                   ml.x + ml.ts_width + (0 if inner else 0.2 * sp), start=True)
            if ml.ts_width:
                self._paint_time_signature(painter, system, ml.x + ml.ts_width / 2 + 0.1 * sp,
                                           score.time_sig_of(mi))

        painter.setPen(INK)
        smufl.draw_glyph(painter, smufl.CLEF_PERCUSSION,
                         QPointF(system.x0 + 1.0 * sp, system.top + 2 * sp), self.font)
        if layout.numbers and system.index > 0 and system.measures:
            font = QFont(self.text_font)
            font.setPixelSize(max(1, round(sp * 1.15)))
            painter.setFont(font)
            painter.drawText(QPointF(system.x0, top - 1.2 * sp), str(system.measures[0] + 1))

    def _paint_time_signature(self, painter, system, cx: float, ts: tuple):
        painter.setPen(INK)
        for value, line in ((ts[0], 2), (ts[1], 6)):
            glyphs = "".join(smufl.TIME_SIG_DIGITS[int(d)] for d in str(value))
            smufl.draw_glyph_centered(painter, glyphs, QPointF(cx, self.line_y(system, line)),
                                      self.font)

    def _paint_repeat(self, painter, system, x: float, start: bool):
        sp = self.sp
        top = system.top
        thick, gap, thin = 0.5 * sp, 0.4 * sp, smufl.THIN_BARLINE_THICKNESS * sp
        d = 1 if start else -1
        thick_x = x if start else x - thick
        thin_x = x + d * (thick + gap)
        dot_x = thin_x + d * 0.65 * sp
        painter.fillRect(QRectF(thick_x, top, thick, 4 * sp), INK)
        painter.setPen(QPen(INK, thin, Qt.SolidLine, Qt.FlatCap))
        painter.drawLine(QPointF(thin_x, top), QPointF(thin_x, top + 4 * sp))
        painter.setPen(Qt.NoPen)
        painter.setBrush(INK)
        for line in (3, 5):
            painter.drawEllipse(QPointF(dot_x, self.line_y(system, line)), 0.22 * sp, 0.22 * sp)

    @staticmethod
    def _ending_runs(score: Score) -> list:
        runs = []
        for mi, measure in enumerate(score.measures):
            if not measure.ending:
                continue
            if runs and runs[-1][0] == measure.ending and runs[-1][2] == mi - 1:
                runs[-1][2] = mi
            else:
                runs.append([measure.ending, mi, mi])
        return runs

    def _paint_endings(self, painter, score, layout):
        runs = self._ending_runs(score)
        if not runs:
            return
        sp = self.sp
        tops = {}
        for mi, _, _, c, _ in score.chords():
            g = self.geoms.get(id(c))
            if g is not None:
                tops[mi] = min(tops.get(mi, g.top), g.top)
        font = QFont(self.text_font)
        font.setPixelSize(max(1, round(sp * 1.3)))
        hook = 1.3 * sp
        pieces, line_y = [], {}
        for number, first, last in runs:
            for system in layout.systems:
                inside = [mi for mi in system.measures if first <= mi <= last]
                if not inside:
                    continue
                highest = min([tops.get(mi, system.top) for mi in inside] + [system.top])
                y = min(system.top - 6.2 * sp, highest - 0.8 * sp - hook)
                y = max(y, system.top - (self.STAFF_ABOVE - 0.4) * sp)
                line_y[system.index] = min(line_y.get(system.index, y), y)
                pieces.append((number, first, last, system, inside))
        for number, first, last, system, inside in pieces:
            starts, ends = inside[0] == first, inside[-1] == last
            a, b = layout.measures[inside[0]], layout.measures[inside[-1]]
            x1 = a.x + 0.3 * sp if starts else system.content_x
            x2 = b.x + b.width - 0.3 * sp
            y = line_y[system.index]
            points = ([QPointF(x1, y + hook)] if starts else []) + \
                [QPointF(x1, y), QPointF(x2, y)] + ([QPointF(x2, y + hook)] if ends else [])
            painter.setPen(QPen(INK, 0.13 * sp, Qt.SolidLine, Qt.FlatCap, Qt.MiterJoin))
            painter.setBrush(Qt.NoBrush)
            painter.drawPolyline(points)
            if starts:
                painter.setFont(font)
                painter.drawText(QPointF(x1 + 0.45 * sp, y + 1.35 * sp), f"{number}.")

    def _paint_measure(self, painter, score, layout, ml, selected):
        sp = self.sp
        system = layout.systems[ml.system]
        measure = score.measures[ml.index]
        both = bool(measure.voices[0]) and bool(measure.voices[1])
        if not measure.voices[0]:
            offset = -2 * sp if measure.voices[1] else 0
            bounds = smufl.glyph_bounds(smufl.RESTS[1], self.font)
            lead = ml.ts_width + ml.repeat_width
            origin = QPointF(ml.x + lead + (ml.width - lead) / 2 - bounds.center().x(),
                             system.top + sp + offset)
            painter.setPen(SELECT_COLORS[0] if ("mrest", ml.index) in selected else INK)
            smufl.draw_glyph(painter, smufl.RESTS[1], origin, self.font)
            rect = bounds.translated(origin).adjusted(-0.4 * sp, -0.4 * sp, 0.4 * sp, 0.4 * sp)
            self.hits.append(Hit(rect, "rest", voice=0, measure=ml.index))
        for voice, events in enumerate(measure.voices):
            if events:
                self._paint_voice(painter, score, layout, ml, system, voice, events,
                                  both, selected)

    def _flatten(self, events):
        for s, item in onsets(events):
            if isinstance(item, TupletGroup):
                for ls, c in onsets(item.events):
                    yield s + ls * item.ratio, c, item
            else:
                yield s, item, None

    def _paint_voice(self, painter, score, layout, ml, system, voice, events, both, selected):
        sp = self.sp
        flat = list(self._flatten(events))
        geoms = {}
        for tick, c, group in flat:
            x = ml.ticks.get(tick, ml.x)
            self.positions[id(c)] = (system.index, x)
            if c.is_rest:
                self._paint_rest(painter, system, x, c, voice, both, selected)
            else:
                geoms[id(c)] = self._chord_geom(system, x, c, voice)

        beam_groups = self._beam_groups(score, flat, score.time_sig_of(ml.index))
        for group, _ in beam_groups:
            self._apply_beam(group, geoms)
            self.beam_groups.append([c for _, c in group])
        for tick, c, _ in flat:
            if not c.is_rest:
                g = geoms[id(c)]
                self.geoms[id(c)] = g
                self._paint_chord(painter, system, c, g, voice, selected)
        for group, beat in beam_groups:
            self._paint_beam(painter, group, geoms, beat)
        for s, item in onsets(events):
            if isinstance(item, TupletGroup):
                self._paint_tuplet(painter, system, ml, item, s, voice, geoms, flat)
    def _paint_rest(self, painter, system, x, c, voice, both, selected):
        sp = self.sp
        glyph = smufl.RESTS[int(1 / c.base)]
        offset = (-2 * sp if voice == 0 else 2 * sp) if both else 0
        baseline = system.top + (sp if c.base == 1 else 2 * sp) + offset
        bounds = smufl.glyph_bounds(glyph, self.font)
        gx = x + self.head_w / 2 - bounds.center().x()
        color = SELECT_COLORS[voice] if id(c) in selected else INK
        painter.setPen(color)
        smufl.draw_glyph(painter, glyph, QPointF(gx, baseline), self.font)
        rect = bounds.translated(gx, baseline).adjusted(-0.3 * sp, -0.3 * sp, 0.3 * sp, 0.3 * sp)
        if c.dots:
            smufl.draw_glyph(painter, smufl.AUGMENTATION_DOT,
                             QPointF(rect.right() + 0.1 * sp, system.top + 1.5 * sp + offset),
                             self.font)
        self.hits.append(Hit(rect, "rest", chord=c, voice=voice))
        if c.text:
            self._paint_text(painter, system, x, c, selected)
    def _head_glyph(self, head: str, base: Fraction) -> str:
        whole, half, black = smufl.NOTEHEADS[head]
        return whole if base >= 1 else half if base == F(1, 2) else black

    def _chord_geom(self, system, x, c, voice) -> ChordGeom:
        sp = self.sp
        up = (voice == 0) != c.stem_flipped
        head_w = max(smufl.glyph_advance(self._head_glyph(n.head, c.base), self.font)
                     for n in c.notes)
        g = ChordGeom(system.index, x, head_w, up)
        for n in c.notes:
            g.ys[n.instrument] = self.line_y(system, n.info.line)
        g.min_y, g.max_y = min(g.ys.values()), max(g.ys.values())
        g.has_stem = c.base < 1
        stem_w = smufl.STEM_THICKNESS * sp
        g.stem_x = x + head_w - stem_w / 2 if up else x + stem_w / 2
        levels = BEAM_LEVELS.get(c.base, 0)
        length = 3.5 + {3: 0.5, 4: 1.25}.get(levels, 0)
        if c.tremolo and levels:
            length += 1.0
        g.tip = g.min_y - length * sp if up else g.max_y + length * sp
        return g

    def _paint_chord(self, painter, system, c, g, voice, selected):
        sp = self.sp
        ink_sel = SELECT_COLORS[voice]
        notes = sorted(c.notes, key=lambda n: -n.info.line if g.stem_up else n.info.line)
        prev_line, prev_shift = None, False
        head_right = g.x + g.head_w
        for n in notes:
            line = n.info.line
            shift = prev_line is not None and abs(line - prev_line) == 1 and not prev_shift
            hx = g.x + ((g.head_w - smufl.STEM_THICKNESS * sp) if g.stem_up else
                        -(g.head_w - smufl.STEM_THICKNESS * sp)) * shift
            prev_line, prev_shift = line, shift
            y = self.line_y(system, line)
            self._paint_ledgers(painter, system, hx, line)
            glyph = self._head_glyph(n.head, c.base)
            bounds = smufl.glyph_bounds(glyph, self.font)
            painter.setPen(ink_sel if id(n) in selected else INK)
            smufl.draw_glyph(painter, glyph, QPointF(hx, y), self.font)
            rect = bounds.translated(hx, y).adjusted(-0.25 * sp, -0.25 * sp, 0.25 * sp, 0.25 * sp)
            self.hits.append(Hit(rect, "note", chord=c, note=n, voice=voice))
            head_right = max(head_right, hx + bounds.right())
            if n.grace:
                painter.setPen(ink_sel if id(n) in selected else INK)
                gx = g.x - 1.55 * sp
                draw_grace(painter, gx, y, n.grace, self._head_glyph(n.head, F(1, 4)),
                           sp * GRACE_SCALE, up=g.stem_up)

        painter.setPen(INK)
        if c.dots:
            for n in c.notes:
                line = n.info.line
                if line % 2 == 0:
                    line += -1 if g.stem_up else 1
                smufl.draw_glyph(painter, smufl.AUGMENTATION_DOT,
                                 QPointF(head_right + 0.35 * sp, self.line_y(system, line)),
                                 self.font)
        if g.has_stem:
            stem_w = smufl.STEM_THICKNESS * sp
            start = g.max_y if g.stem_up else g.min_y
            top, bottom = sorted((start, g.tip))
            painter.fillRect(QRectF(g.stem_x - stem_w / 2, top, stem_w, bottom - top), INK)
            levels = BEAM_LEVELS.get(c.base, 0)
            if levels and not g.beamed:
                flag = smufl.FLAGS[levels][0 if g.stem_up else 1]
                smufl.draw_glyph(painter, flag, QPointF(g.stem_x - stem_w / 2, g.tip), self.font)
        if c.tremolo:
            self._paint_tremolo(painter, c, g)
        g.top = min(g.min_y - 0.6 * sp, g.tip if g.has_stem and g.stem_up else g.min_y)
        self._paint_articulations(painter, system, c, g)
        if c.text:
            self._paint_text(painter, system, g.x, c, selected)

    def _paint_ledgers(self, painter, system, x, line, color=INK):
        sp = self.sp
        painter.setPen(QPen(color, 0.16 * sp, Qt.SolidLine, Qt.FlatCap))
        ledgers = list(range(-2, line - 1, -2)) if line <= -2 else \
            list(range(10, line + 1, 2)) if line >= 10 else []
        for l in ledgers:
            y = self.line_y(system, l)
            painter.drawLine(QPointF(x - 0.35 * sp, y), QPointF(x + self.head_w + 0.35 * sp, y))

    def _paint_tremolo(self, painter, c, g):
        sp = self.sp
        glyph = smufl.BUZZ_ROLL if c.tremolo == "buzz" else \
            smufl.TREMOLO_STROKES[TREMOLO_STROKES[c.tremolo]]
        if g.has_stem:
            y = g.min_y - 1.6 * sp if g.stem_up else g.max_y + 1.6 * sp
            x = g.stem_x
        else:
            y = g.min_y - 1.6 * sp
            x = g.x + g.head_w / 2
        painter.setPen(INK)
        smufl.draw_glyph_centered(painter, glyph, QPointF(x, y), self.font)

    def _paint_articulations(self, painter, system, c, g):
        sp = self.sp
        arts = [a for a in smufl.ARTICULATION_ORDER if a in c.articulations]
        if not arts:
            return
        above = g.stem_up
        x = g.stem_x if g.has_stem else g.x + g.head_w / 2
        if above:
            ref = min(g.tip if g.has_stem else g.min_y - 0.5 * sp, system.top) - 0.5 * sp
        else:
            ref = max(g.tip if g.has_stem else g.max_y + 0.5 * sp, system.top + 4 * sp) + 0.5 * sp
        painter.setPen(INK)
        for a in arts:
            glyph = smufl.ARTICULATIONS[a][0 if above else 1]
            b = smufl.glyph_bounds(glyph, self.font)
            cy = ref - b.height() / 2 if above else ref + b.height() / 2
            smufl.draw_glyph_centered(painter, glyph, QPointF(x, cy), self.font)
            ref = ref - b.height() - 0.35 * sp if above else ref + b.height() + 0.35 * sp
        if above:
            g.top = min(g.top, ref)

    def _paint_text(self, painter, system, x, c, selected):
        sp = self.sp
        painter.setFont(self.text_font)
        color = SELECT_COLORS[0] if ("text", id(c)) in selected else INK
        painter.setPen(color)
        baseline = system.top - 7.5 * sp
        painter.drawText(QPointF(x, baseline), c.text)
        fm_rect = painter.fontMetrics().boundingRect(c.text)
        rect = QRectF(fm_rect).translated(x, baseline).adjusted(-3, -3, 3, 3)
        self.hits.append(Hit(rect, "text", chord=c))
    def _beam_unit(self, ts: tuple, base: Fraction) -> Fraction:
        n, d = ts
        if d >= 8 and n % 3 == 0 and n > 3:
            return F(3, d)
        if base == F(1, 8):
            if (n, d) == (4, 4):
                return F(1, 2)
            if (n, d) == (3, 4) or d >= 8:
                return F(n, d)
        return max(F(1, d), F(1, 8)) if d >= 8 else F(1, d)

    def _beam_groups(self, score: Score, flat, ts: Optional[tuple] = None) -> list:
        ts = ts or (score.numerator, score.denominator)
        eighth_unit = self._beam_unit(ts, F(1, 8))
        groups, current, key = [], [], None
        for tick, c, tup in flat:
            beamable = not c.is_rest and c.base <= F(1, 8) and c.beam != "none"
            k = ("t", tup) if tup is not None else ("m", int(tick // eighth_unit))
            if beamable and current and c.beam != "start" and (k == key or c.beam == "join"):
                current.append((tick, c))
            else:
                if len(current) > 1:
                    groups.append((key, current))
                current = [(tick, c)] if beamable else []
            key = k
        if len(current) > 1:
            groups.append((key, current))
        beat = self._beam_unit(ts, F(1, 16))
        result = []
        for k, grp in groups:
            sextuplet = k[0] == "t" and k[1].actual == 6
            user_joined = any(c.beam == "join" for _, c in grp[1:])
            if sextuplet or user_joined or len(grp) <= self.MAX_AUTO_BEAM:
                result.append((grp, None if k[0] == "t" else beat))
            else:
                result.extend((part, beat) for part in self._cap_group(grp, beat))
        return result

    MAX_AUTO_BEAM = 4

    def _cap_group(self, grp, beat) -> list:
        cap = self.MAX_AUTO_BEAM
        chunks, current, key = [], [], None
        for tick, c in grp:
            k = int(tick // beat)
            if current and k != key:
                chunks.append(current)
                current = []
            current.append((tick, c))
            key = k
        if current:
            chunks.append(current)

        parts, pack = [], []
        for chunk in chunks:
            if len(chunk) > cap:
                parts.append(pack)
                parts.extend(chunk[i:i + cap] for i in range(0, len(chunk), cap))
                pack = []
            elif len(pack) + len(chunk) <= cap:
                pack = pack + chunk
            else:
                parts.append(pack)
                pack = chunk
        parts.append(pack)
        return [p for p in parts if len(p) > 1]

    def _apply_beam(self, group, geoms):
        sp = self.sp
        gs = [geoms[id(c)] for _, c in group]
        up = gs[0].stem_up
        max_levels = max(BEAM_LEVELS[c.base] for _, c in group)
        extra = max(0, max_levels - 2) * 0.75
        if up:
            tip = min(g.min_y for g in gs) - (3.5 + extra) * sp
        else:
            tip = max(g.max_y for g in gs) + (3.5 + extra) * sp
        stem_w = smufl.STEM_THICKNESS * sp
        for g in gs:
            g.stem_up, g.tip, g.beamed = up, tip, True
            g.stem_x = g.x + g.head_w - stem_w / 2 if up else g.x + stem_w / 2

    def _paint_beam(self, painter, group, geoms, beat=None):
        sp = self.sp
        gs = [geoms[id(c)] for _, c in group]
        chords = [c for _, c in group]
        beat_of = [0 if beat is None else int(t // beat) for t, _ in group]
        up = gs[0].stem_up
        thick = smufl.BEAM_THICKNESS * sp
        step = 0.75 * sp
        stem_w = smufl.STEM_THICKNESS * sp

        def bar(x1, x2, level):
            y = gs[0].tip + (level - 1) * step if up else gs[0].tip - (level - 1) * step - thick
            painter.fillRect(QRectF(x1, y, x2 - x1, thick), INK)

        bar(gs[0].stem_x - stem_w / 2, gs[-1].stem_x + stem_w / 2, 1)
        max_levels = max(BEAM_LEVELS[c.base] for c in chords)
        for level in range(2, max_levels + 1):
            i = 0
            while i < len(chords):
                if BEAM_LEVELS[chords[i].base] < level:
                    i += 1
                    continue
                j = i
                while j + 1 < len(chords) and BEAM_LEVELS[chords[j + 1].base] >= level \
                        and beat_of[j + 1] == beat_of[i]:
                    j += 1
                if j > i:
                    bar(gs[i].stem_x - stem_w / 2, gs[j].stem_x + stem_w / 2, level)
                else:
                    stub = 1.1 * sp
                    first_in_beat = i == 0 or beat_of[i - 1] != beat_of[i]
                    if first_in_beat and i + 1 < len(chords):
                        bar(gs[i].stem_x - stem_w / 2, gs[i].stem_x + stub, level)
                    else:
                        bar(gs[i].stem_x - stub, gs[i].stem_x + stem_w / 2, level)
                i = j + 1
    def _paint_tuplet(self, painter, system, ml, group, start, voice, geoms, flat):
        sp = self.sp
        members = [(t, c) for t, c, g in flat if g is group]
        xs = [ml.ticks.get(t, ml.x) for t, _ in members]
        x1, x2 = xs[0], xs[-1] + self.head_w
        notes = [geoms[id(c)] for _, c in members if not c.is_rest]
        up = voice == 0 if not notes else notes[0].stem_up
        if up:
            y = min([g.tip for g in notes if g.has_stem] + [system.top]) - 1.0 * sp
        else:
            y = max([g.tip for g in notes if g.has_stem] + [system.top + 4 * sp]) + 1.0 * sp
        all_beamed = notes and len(notes) == len(members) and all(g.beamed for g in notes)
        painter.setPen(INK)
        number = "".join(smufl.TUPLET_DIGITS[int(d)] for d in str(group.actual))
        b = smufl.glyph_bounds(number, self.font)
        cx = (x1 + x2) / 2
        smufl.draw_glyph(painter, number, QPointF(cx - b.center().x(),
                                                 y - b.center().y()), self.font)
        if not all_beamed:
            hook = 0.6 * sp if up else -0.6 * sp
            gap = b.width() / 2 + 0.4 * sp
            painter.setPen(QPen(INK, 0.12 * sp))
            painter.drawPolyline([QPointF(x1, y + hook), QPointF(x1, y), QPointF(cx - gap, y)])
            painter.drawPolyline([QPointF(cx + gap, y), QPointF(x2, y), QPointF(x2, y + hook)])
    def _paint_ties(self, painter, score, layout):
        sp = self.sp
        for voice in (0, 1):
            chords = [c for _, v, _, c, _ in score.chords() if v == voice]
            for c, nxt in zip(chords, chords[1:]):
                if not c.tie_forward or nxt.is_rest or id(c) not in self.geoms:
                    continue
                g1, g2 = self.geoms[id(c)], self.geoms.get(id(nxt))
                if g2 is None:
                    continue
                for n in c.notes:
                    if n.instrument not in g2.ys:
                        continue
                    d = 1 if g1.stem_up else -1
                    y1 = g1.ys[n.instrument] + d * 0.55 * sp
                    xa = g1.x + g1.head_w + 0.15 * sp
                    if g1.system == g2.system:
                        self._tie_arc(painter, xa, g2.x - 0.15 * sp, y1, d)
                    else:
                        s1, s2 = layout.systems[g1.system], layout.systems[g2.system]
                        self._tie_arc(painter, xa, s1.x1 - 0.3 * sp, y1, d)
                        y2 = g2.ys[n.instrument] + d * 0.55 * sp
                        self._tie_arc(painter, s2.content_x - 0.8 * sp, g2.x - 0.15 * sp, y2, d)

    def _tie_arc(self, painter, x1, x2, y, d):
        sp = self.sp
        if x2 - x1 < 0.5 * sp:
            return
        h = min(0.9 * sp, 0.2 * (x2 - x1)) * d
        t = 0.16 * sp * d
        path = QPainterPath(QPointF(x1, y))
        path.cubicTo(x1 + (x2 - x1) * 0.25, y + h, x2 - (x2 - x1) * 0.25, y + h, x2, y)
        path.cubicTo(x2 - (x2 - x1) * 0.25, y + h + t, x1 + (x2 - x1) * 0.25, y + h + t, x1, y)
        painter.setPen(Qt.NoPen)
        painter.setBrush(INK)
        painter.drawPath(path)
    def _chord_end_x(self, score, layout, chord) -> tuple:
        for mi, v, group, c, t in score.chords():
            if c is chord:
                length = c.length * (group.ratio if group else 1)
                end = t + length
                ml = layout.measures[mi]
                cap = score.capacity_of(mi)
                if end >= cap:
                    return ml.system, ml.x + ml.width - 0.8 * self.sp
                return ml.system, self.tick_x(layout, mi, end, cap)
        return None

    def _paint_hairpins(self, painter, score, layout, selected):
        sp = self.sp
        for hp in score.hairpins:
            g = self.geoms.get(id(hp.start))
            end = self._chord_end_x(score, layout, hp.end)
            if g is None or end is None:
                continue
            end_sys, end_x = end
            color = SELECT_COLORS[0] if id(hp) in selected else INK
            pieces = []
            for si in range(g.system, end_sys + 1):
                s = layout.systems[si]
                xa = g.x if si == g.system else s.content_x
                xb = end_x if si == end_sys else s.x1 - 0.5 * sp
                pieces.append((s, xa, xb))
            total = sum(xb - xa for _, xa, xb in pieces) or 1
            done = 0.0
            for s, xa, xb in pieces:
                y = s.top + 9.5 * sp
                h = 0.65 * sp
                fa, fb = done / total, (done + xb - xa) / total
                done += xb - xa
                if hp.kind == "decrescendo":
                    fa, fb = 1 - fa, 1 - fb
                painter.setPen(QPen(color, 0.14 * sp, Qt.SolidLine, Qt.RoundCap))
                painter.drawLine(QPointF(xa, y - h * fa), QPointF(xb, y - h * fb))
                painter.drawLine(QPointF(xa, y + h * fa), QPointF(xb, y + h * fb))
                self.hits.append(Hit(QRectF(xa, y - h - 0.4 * sp, xb - xa, 2 * h + 0.8 * sp),
                                     "hairpin", hairpin=hp))
