from fractions import Fraction

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QLineEdit, QMenu, QScrollArea, QWidget

from ..notation.engraver import Engraver
from . import style


class ScoreView(QWidget):

    BASE_STAFF_SPACE = 11.0
    DEFAULT_ZOOM = 1.5
    MIN_ZOOM, MAX_ZOOM = 1.0, 5.0
    ZOOM_STEP = 1.1

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.zoom = self.DEFAULT_ZOOM
        self.engraver = Engraver(self.BASE_STAFF_SPACE * self.zoom)
        self.layout_data = None
        self.hover = None
        self._mouse_pos = None
        self._drag_origin = None
        self._drag_rect = None
        self._split_parts = []
        self._text_editor = None
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        controller.changed.connect(self.relayout)
        controller.state_changed.connect(self._update_hover)
        controller.text_edit_requested.connect(self.edit_text)

    def _scroll_area(self):
        widget = self.parentWidget()
        while widget is not None and not isinstance(widget, QScrollArea):
            widget = widget.parentWidget()
        return widget

    def _layout_width(self) -> int:
        area = self._scroll_area()
        return area.viewport().width() if area is not None else self.width()

    def relayout(self):
        width = max(self._layout_width(), 400)
        self.layout_data = self.engraver.layout(self.controller.score, width)
        right = max(s.x1 for s in self.layout_data.systems) + \
            self.engraver.MARGIN_X * self.engraver.sp
        self.setMinimumSize(int(right) if right > width else 0, int(self.layout_data.height))
        self._update_hover()
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.layout_data is None or abs(self.layout_data.width - self._layout_width()) > 1:
            self.relayout()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(style.SCORE_BG))
        if self.layout_data is None:
            self.relayout()
        c = self.controller
        self.engraver.paint(painter, c.score, self.layout_data, c.selected_keys(),
                            c.cursor if c.input_mode else None,
                            self.hover if c.input_mode else None)
        if self._drag_rect is not None:
            painter.setPen(QPen(QColor(21, 101, 216, 200), 1, Qt.DashLine))
            painter.setBrush(QColor(21, 101, 216, 35))
            painter.drawRect(self._drag_rect)

    def set_zoom(self, zoom: float, anchor: QPointF = None):
        zoom = min(self.MAX_ZOOM, max(self.MIN_ZOOM, zoom))
        if abs(zoom - self.zoom) < 1e-6:
            return
        self._close_text_editor(commit=True)
        area = self._scroll_area()
        old_height = self.layout_data.height if self.layout_data else 1
        if anchor is not None and area is not None:
            ratio = anchor.y() / old_height
            in_view = anchor.y() - area.verticalScrollBar().value()
        self.zoom = zoom
        self.engraver = Engraver(self.BASE_STAFF_SPACE * zoom)
        self.relayout()
        if anchor is not None and area is not None:
            target = int(ratio * self.layout_data.height - in_view)
            QTimer.singleShot(0, lambda: area.verticalScrollBar().setValue(target))

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            steps = event.angleDelta().y() / 120
            if steps:
                self.set_zoom(self.zoom * self.ZOOM_STEP ** steps, QPointF(event.position()))
            event.accept()
            return
        event.ignore()

    def _input_target(self, pos: QPointF):
        found = self.engraver.staff_position(self.layout_data, pos)
        if found is None:
            return None
        measure, line = found
        c = self.controller
        inst = c.instrument_for_line(line)
        ticks = c.input_ticks(measure, inst.voice if inst else 0)
        tick = self.engraver.nearest_tick(self.layout_data, measure, ticks, pos.x(),
                                          c.score.capacity)
        return measure, tick, line

    def _update_hover(self):
        shadow = None
        c = self.controller
        if self._mouse_pos is not None and c.input_mode and self.layout_data is not None:
            hit = self.engraver.hit_test(self._mouse_pos)
            if hit is None or hit.kind == "rest":
                target = self._input_target(self._mouse_pos)
                if target is not None:
                    shadow = c.shadow_for(*target)
        if shadow != self.hover:
            self.hover = shadow
            self.update()

    def mouseMoveEvent(self, event):
        self._mouse_pos = QPointF(event.position())
        if self._drag_origin is not None:
            self._drag_rect = QRectF(self._drag_origin, self._mouse_pos).normalized()
            self.update()
            return
        self._update_hover()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton or self._drag_origin is None:
            return
        rect, add = self._drag_rect, bool(event.modifiers() & Qt.ControlModifier)
        self._drag_origin = self._drag_rect = None
        if rect is not None and rect.width() + rect.height() > 6:
            self.controller.select_hits(
                [h for h in self.engraver.hits if h.rect.intersects(rect)], add)
        elif not add:
            self.controller.clear_selection()
        self.update()

    def leaveEvent(self, event):
        self._mouse_pos = None
        self._update_hover()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self.setFocus()
        if event.button() == Qt.RightButton:
            self._beam_menu(QPointF(event.position()), event.globalPosition().toPoint())
            return
        if event.button() != Qt.LeftButton:
            return
        c = self.controller
        pos = QPointF(event.position())
        add = bool(event.modifiers() & Qt.ControlModifier)
        hit = self.engraver.hit_test(pos)

        if c.select_mode:
            if hit is not None:
                c.click_hit(hit, add)
            else:
                self._drag_origin = pos
                self._drag_rect = None
            return

        if hit is not None and hit.kind != "rest":
            c.click_hit(hit, add)
            return
        target = self._input_target(pos)
        if target is None:
            c.clear_selection()
            return
        measure, tick, line = target
        inst = c.instrument_for_line(line)
        if inst is not None:
            c.input_at(measure, tick, inst)
        else:
            c.click_position(measure, tick)

    def beam_menu_actions(self, pos: QPointF) -> list:
        hit = self.engraver.hit_test(pos)
        if hit is None or hit.kind != "note":
            return []
        c = self.controller
        selected = c.selected_chords()
        if hit.chord not in selected:
            c.click_hit(hit, False)
            selected = c.selected_chords()
        geoms = self.engraver.geoms
        beamable = [x for x in selected if x.base <= Fraction(1, 8)]
        beamed = [x for x in selected if id(x) in geoms and geoms[id(x)].beamed]
        self._split_parts = self._splittable(selected)
        return (["묶기"] if len(beamable) >= 2 else []) + \
            (["묶음 분리"] if self._split_parts else []) + \
            (["묶음 풀기"] if beamed else [])

    def _splittable(self, selected) -> list:
        chosen = {id(x) for x in selected}
        parts = []
        for group in self.engraver.beam_groups:
            picked = [i for i, c in enumerate(group) if id(c) in chosen]
            if len(picked) >= 2 and picked[-1] - picked[0] + 1 < len(group):
                parts.append((group, picked[0], picked[-1]))
        return parts

    def _beam_menu(self, pos: QPointF, global_pos):
        actions = self.beam_menu_actions(pos)
        if not actions:
            return
        menu = QMenu(self)
        menu.setFont(QFont(style.BUTTON_FONT_FAMILY, 10))
        parts = self._split_parts
        slots = {"묶기": self.controller.join_beams,
                 "묶음 분리": lambda: self.controller.split_beams(parts),
                 "묶음 풀기": self.controller.unbeam}
        for name in actions:
            menu.addAction(name, slots[name])
        menu.exec(global_pos)

    def mouseDoubleClickEvent(self, event):
        hit = self.engraver.hit_test(QPointF(event.position()))
        if hit is not None and hit.kind == "text":
            self.edit_text(hit.chord)

    def edit_text(self, chord):
        self._close_text_editor(commit=False)
        sp = self.engraver.sp
        system_index, x = self.engraver.positions.get(id(chord), (0, 40.0))
        top = self.layout_data.systems[system_index].top
        editor = QLineEdit(self)
        editor.setFont(QFont("NanumSquare", max(9, round(sp * 1.0))))
        editor.setText(chord.text or "")
        editor.setPlaceholderText("텍스트 입력")
        editor.setStyleSheet("QLineEdit { background: #ffffff; border: 1px solid #1565d8;"
                             " border-radius: 3px; padding: 1px 4px; }")
        editor.resize(int(sp * 20), int(sp * 2.4))
        editor.move(int(x - 4), int(top - 7.5 * sp - sp * 1.8))
        editor.returnPressed.connect(lambda: self._close_text_editor(commit=True))
        editor.editingFinished.connect(lambda: self._close_text_editor(commit=True))
        editor.chord = chord
        editor.show()
        editor.setFocus()
        editor.selectAll()
        self._text_editor = editor

    def _close_text_editor(self, commit: bool):
        editor, self._text_editor = self._text_editor, None
        if editor is None:
            return
        if commit:
            self.controller.set_text(editor.chord, editor.text())
        editor.deleteLater()
        self.setFocus()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self._text_editor is not None:
            self._close_text_editor(commit=False)
            return
        super().keyPressEvent(event)
