import copy
from dataclasses import dataclass
from fractions import Fraction
from typing import Callable, Optional

from PySide6.QtCore import QObject, Signal

from ..notation.engraver import Shadow
from ..notation.model import (Chord, EditError, Hairpin, INSTRUMENT_BY_NAME, INSTRUMENTS,
                              Measure, Note,
                              Score, ScoreEditor, EXCLUSIVE_ARTICULATIONS, TUPLET_KINDS,
                              TupletGroup, notated_length, onsets)

F = Fraction


@dataclass(eq=False)
class Selected:
    kind: str
    chord: Optional[Chord] = None
    note: Optional[Note] = None
    hairpin: Optional[Hairpin] = None
    voice: int = 0
    measure: int = -1

    def key(self):
        if self.kind == "note":
            return id(self.note)
        if self.kind == "rest":
            return id(self.chord)
        if self.kind == "mrest":
            return ("mrest", self.measure)
        if self.kind == "hairpin":
            return id(self.hairpin)
        return ("text", id(self.chord))

    def same(self, other: "Selected") -> bool:
        return self.key() == other.key()


class PresetController(QObject):
    changed = Signal()
    state_changed = Signal()
    message = Signal(str)
    alert = Signal(str)
    text_edit_requested = Signal(object)

    UNDO_LIMIT = 200
    _clipboard = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.score = Score()
        self.editor = ScoreEditor(self.score)
        self.duration = F(1, 8)
        self.dot = False
        self.rest_mode = False
        self.rimshot = False
        self.tremolo_kind = "tremolo16"
        self.grace_kind = "acciaccatura"
        self.tuplet_kind = "triplet"
        self.cursor = (0, F(0))
        self.select_mode = False
        self.selection: list = []
        self.last_input: Optional[tuple] = None
        self.last_instrument = None
        self._undo: list = []
        self._redo: list = []
        self.confirm_overflow: Callable[[], bool] = lambda: True
        self.choose_paste_overflow: Callable[[], str] = lambda: "extend"

    def load_score(self, score: Score):
        self.score = score
        self.editor = ScoreEditor(score)
        self.cursor = (0, F(0))
        self.selection = []
        self.last_input = None
        self._undo.clear()
        self._redo.clear()
        self.changed.emit()
        self.state_changed.emit()

    def _snapshot(self):
        return copy.deepcopy(self.score), self.cursor

    def _restore(self, snap):
        score, cursor = copy.deepcopy(snap[0]), snap[1]
        self.score = score
        self.editor = ScoreEditor(score)
        self.cursor = cursor
        self.selection = []
        self.last_input = None

    def _edit(self, fn: Callable[[], None]) -> bool:
        before = self._snapshot()
        try:
            fn()
        except EditError as e:
            self._restore(before)
            if e.message:
                self.message.emit(e.message)
            self.changed.emit()
            return False
        self.editor.cleanup()
        self._clamp_cursor()
        self._prune_selection()
        self._undo.append(before)
        del self._undo[:-self.UNDO_LIMIT]
        self._redo.clear()
        self.changed.emit()
        return True

    def _clamp_cursor(self):
        m, t = self.cursor
        m = min(m, len(self.score.measures) - 1)
        self.cursor = (m, min(t, self.score.capacity))

    def _prune_selection(self):
        alive = {id(c) for _, _, _, c, _ in self.score.chords()}
        hairpins = {id(h) for h in self.score.hairpins}
        kept = []
        for s in self.selection:
            if s.kind == "hairpin":
                if id(s.hairpin) in hairpins:
                    kept.append(s)
            elif s.kind == "mrest":
                if s.measure < len(self.score.measures) and \
                        not self.score.measures[s.measure].voices[0]:
                    kept.append(s)
            elif id(s.chord) in alive:
                if s.kind == "note" and s.note not in s.chord.notes:
                    continue
                if s.kind == "rest" and not s.chord.is_rest:
                    continue
                kept.append(s)
        self.selection = kept

    def selected_keys(self) -> set:
        return {s.key() for s in self.selection}

    def selected_chords(self, include_rests=False) -> list:
        seen, result = set(), []
        for s in self.selection:
            if s.kind in ("note", "rest") and id(s.chord) not in seen:
                if include_rests or not s.chord.is_rest:
                    seen.add(id(s.chord))
                    result.append(s.chord)
        return result

    def _select_chord(self, chord: Chord, voice: int):
        if chord.is_rest:
            self.selection = [Selected("rest", chord, voice=voice)]
        else:
            self.selection = [Selected("note", chord, n, voice=voice) for n in chord.notes]

    @property
    def input_mode(self) -> bool:
        return not self.select_mode

    def set_select_mode(self, on: bool):
        self.select_mode = on
        self.changed.emit()
        self.state_changed.emit()

    def _editing_selection(self) -> bool:
        return self.select_mode and bool(self.selected_chords(include_rests=True))

    def instrument_for_line(self, line: int):
        candidates = [i for i in INSTRUMENTS.values() if i.line == line]
        if not candidates:
            return None
        if self.last_instrument in candidates:
            return self.last_instrument
        return candidates[0]

    def shadow_for(self, measure: int, tick: Fraction, line: int) -> Optional[Shadow]:
        inst = self.instrument_for_line(line)
        if self.select_mode or inst is None:
            return None
        head = "x" if self.rimshot and inst.key == "snare" else inst.head
        base, dots = self.duration, 1 if self.dot else 0
        existing = self._chord_to_join(measure, tick, inst.voice)
        if existing is not None:
            base, dots = existing.base, existing.dots
        return Shadow(measure, tick, line, head, base, dots, inst.voice, rest=self.rest_mode)

    def input_ticks(self, measure: int, voice: int) -> list:
        cap = self.score.capacity
        ticks = {t for m, _, _, _, t in self.score.chords() if m == measure}
        tuplets = [(s, s + item.length)
                   for s, item in onsets(self.score.measures[measure].voices[voice])
                   if isinstance(item, TupletGroup)]
        step = self.duration
        k = 0
        while k * step < cap:
            t = k * step
            if not any(s < t < e for s, e in tuplets):
                ticks.add(t)
            k += 1
        return sorted(ticks)

    def _chord_to_join(self, measure: int, tick: Fraction, voice: int) -> Optional[Chord]:
        if self.rest_mode:
            return None
        existing = self.editor.event_at(measure, voice, tick)
        return existing if existing is not None and not existing.is_rest else None

    def input_drum(self, name: str, add_to_chord: bool = False):
        self._input(INSTRUMENT_BY_NAME[name], add_to_chord)

    def input_at(self, measure: int, tick: Fraction, inst):
        self._input(inst, False, at=(measure, tick))

    def _input(self, inst, add_to_chord: bool, at: Optional[tuple] = None):
        voice = inst.voice
        self.last_instrument = inst

        def run():
            same_spot = add_to_chord and at is None and self.last_input is not None
            if same_spot:
                _, m, t, _ = self.last_input
            else:
                m, t = at if at is not None else self.cursor
            existing = self._chord_to_join(m, t, voice)
            if existing is not None:
                note = self.editor.add_note(existing, self._new_note(inst))
                if inst.articulation:
                    existing.articulations.add(inst.articulation)
                if not same_spot:
                    self.cursor = self.editor.cursor_after(existing)
                self.last_input = (existing, m, t, voice)
                self.selection = [Selected("note", existing, note, voice=voice)]
                return
            new = self._new_chord(inst)
            next_cursor = self.editor.insert(m, t, new, voice, self.confirm_overflow)
            if not same_spot:
                self.cursor = next_cursor
            self.last_input = (new, m, t, voice)
            self._select_chord(new, voice)

        self._edit(run)

    def _new_note(self, inst) -> Note:
        return Note(inst.key, rimshot=self.rimshot and inst.key == "snare")

    def _new_chord(self, inst) -> Chord:
        dots = 1 if self.dot else 0
        if self.rest_mode:
            return Chord(self.duration, dots)
        arts = {inst.articulation} if inst.articulation else set()
        return Chord(self.duration, dots, [self._new_note(inst)], arts)

    @staticmethod
    def _selected_from_hit(hit) -> Selected:
        if hit.kind == "hairpin":
            return Selected("hairpin", hairpin=hit.hairpin)
        if hit.kind == "text":
            return Selected("text", hit.chord)
        if hit.kind == "note":
            return Selected("note", hit.chord, hit.note, voice=hit.voice)
        if hit.chord is None:
            return Selected("mrest", measure=hit.measure)
        return Selected("rest", hit.chord, voice=hit.voice)

    def click_hit(self, hit, add: bool):
        item = self._selected_from_hit(hit)
        if item.kind == "mrest":
            self.cursor = (item.measure, F(0))
        if add:
            existing = [s for s in self.selection if s.same(item)]
            if existing:
                self.selection.remove(existing[0])
            else:
                self.selection.append(item)
        else:
            self.selection = [item]
        if item.chord is not None:
            loc = self.editor.locate(item.chord)
            self.cursor = (loc.measure, loc.onset)
            self.last_input = (item.chord, loc.measure, loc.onset, loc.voice)
        self.changed.emit()

    def select_hits(self, hits, add: bool):
        items = [self._selected_from_hit(h) for h in hits if h.kind in ("note", "rest")]
        if not add:
            self.selection = []
        for item in items:
            if not any(s.same(item) for s in self.selection):
                self.selection.append(item)
        self.changed.emit()

    def click_position(self, measure: int, tick: Fraction):
        self.cursor = (measure, tick)
        self.selection = []
        self.last_input = None
        self.changed.emit()

    def clear_selection(self):
        self.selection = []
        self.changed.emit()

    def set_duration(self, base: Fraction):
        self.duration = base
        if self._editing_selection():
            def run():
                for c in self.selected_chords(include_rests=True):
                    self.editor.change_duration(c, base, c.dots, self.confirm_overflow)
            self._edit(run)
        self.state_changed.emit()

    def toggle_dot(self):
        if self._editing_selection():
            chords = self.selected_chords(include_rests=True)
            self.dot = not chords[0].dots

            def run():
                for c in chords:
                    self.editor.change_duration(c, c.base, 1 if self.dot else 0,
                                                self.confirm_overflow)
            self._edit(run)
        else:
            self.dot = not self.dot
        self.state_changed.emit()

    def toggle_rest(self):
        if self._editing_selection():
            def run():
                for c in self.selected_chords():
                    c.make_rest()
            self._edit(run)
        else:
            self.rest_mode = not self.rest_mode
        self.state_changed.emit()

    def toggle_rimshot(self):
        snares = [s.note for s in self.selection
                  if s.kind == "note" and s.note.instrument == "snare"]
        if self.select_mode and snares:
            def run():
                value = not snares[0].rimshot
                for n in snares:
                    n.rimshot = value
            self._edit(run)
        else:
            self.rimshot = not self.rimshot
        self.state_changed.emit()

    def _need_chords(self) -> list:
        chords = self.selected_chords()
        if not chords:
            self.message.emit("먼저 음표를 선택하세요.")
        return chords

    def toggle_articulation(self, name: str):
        chords = self._need_chords()
        if not chords:
            return

        def run():
            add = name not in chords[0].articulations
            for c in chords:
                if add:
                    for group in EXCLUSIVE_ARTICULATIONS:
                        if name in group:
                            c.articulations -= group
                    c.articulations.add(name)
                else:
                    c.articulations.discard(name)
        self._edit(run)

    def apply_tremolo(self, kind: Optional[str] = None):
        if kind is not None:
            self.tremolo_kind = kind
            self.state_changed.emit()
        chords = self.selected_chords()
        if not chords:
            if kind is None:
                self.message.emit("먼저 음표를 선택하세요.")
            return
        kind = self.tremolo_kind

        def run():
            value = None if chords[0].tremolo == kind else kind
            for c in chords:
                c.tremolo = value
        self._edit(run)

    def apply_grace(self, kind: Optional[str] = None):
        if kind is not None:
            self.grace_kind = kind
            self.state_changed.emit()
        notes = [s.note for s in self.selection if s.kind == "note"]
        if not notes:
            if kind is None:
                self.message.emit("먼저 음표를 선택하세요.")
            return
        kind = self.grace_kind

        def run():
            value = None if notes[0].grace == kind else kind
            for n in notes:
                n.grace = value
        self._edit(run)

    def flip_direction(self):
        chords = self._need_chords()
        if chords:
            def run():
                for c in chords:
                    c.stem_flipped = not c.stem_flipped
            self._edit(run)

    def apply_tuplet(self, kind: Optional[str] = None):
        if kind is not None:
            self.tuplet_kind = kind
            self.state_changed.emit()
        kind = self.tuplet_kind
        chords = self.selected_chords(include_rests=True)
        if self.select_mode and len(chords) == 1:
            chord = chords[0]

            def run():
                loc = self.editor.locate(chord)
                if loc.group is not None:
                    raise EditError("잇단음표 안에는 잇단음표를 만들 수 없습니다.")
                self.editor.make_tuplet(loc.measure, loc.voice, loc.onset, chord.length,
                                        kind, first=chord)
            self._edit(run)
            return

        m, t = self.cursor
        voice = self.last_input[3] if self.last_input else 0
        span = notated_length(self.duration, 1 if self.dot else 0)

        def run():
            self.editor.make_tuplet(m, voice, t, span, kind)
        if self._edit(run):
            self.duration = span / TUPLET_KINDS[kind][1]
            self.dot = False
            self.state_changed.emit()

    def copy_selection(self):
        chords = self.selected_chords(include_rests=True)
        if not chords:
            self.message.emit("복사할 음표를 먼저 선택하세요.")
            return
        PresetController._clipboard = self.editor.copy_range(chords)
        self.message.emit("복사 완료.")

    def paste(self):
        clip = PresetController._clipboard
        if clip is None:
            self.message.emit("복사한 내용이 없습니다.")
            return
        starts = [self.editor.span_start(c) for c in self.selected_chords(include_rests=True)]
        starts += [s.measure * self.score.capacity for s in self.selection if s.kind == "mrest"]
        if not starts:
            self.alert.emit("위치 지정 필요")
            return
        start = min(starts)

        def run():
            pasted = self.editor.paste(clip, start, self.choose_paste_overflow)
            self.selection = [Selected("note", c, n, voice=self.editor.locate(c).voice)
                              for c in pasted for n in c.notes]
        self._edit(run)

    def join_beams(self):
        chosen = {id(c) for c in self.selected_chords()}
        if len(chosen) < 2:
            return

        def run():
            ranges = {}
            for m, v, _, c, _ in self.score.chords():
                ranges.setdefault((m, v), []).append(c)
            for chords in ranges.values():
                picked = [i for i, c in enumerate(chords) if id(c) in chosen]
                if len(picked) < 2:
                    continue
                first, last = picked[0], picked[-1]
                if chords[first].beam == "none":
                    chords[first].beam = None
                for c in chords[first + 1:last + 1]:
                    if not c.is_rest and c.base <= F(1, 8):
                        c.beam = "join"
        self._edit(run)

    def split_beams(self, parts: list):
        if not parts:
            return

        def run():
            for group, first, last in parts:
                group[first].beam = "start"
                for c in group[first + 1:last + 1]:
                    c.beam = "join"
                if last + 1 < len(group):
                    group[last + 1].beam = "start"
        self._edit(run)

    def unbeam(self):
        chords = self.selected_chords()
        if chords:
            def run():
                for c in chords:
                    c.beam = "none"
            self._edit(run)

    def add_hairpin(self, kind: str):
        chords = self.selected_chords(include_rests=True)
        if not chords:
            self.message.emit("먼저 음표를 선택하세요.")
            return
        order = {id(c): i for i, (_, _, _, c, _) in enumerate(self.score.chords())}
        chords.sort(key=lambda c: order[id(c)])
        if chords[0].is_rest:
            self.message.emit("헤어핀은 음표에서 시작해야 합니다.")
            return
        self._edit(lambda: self.score.hairpins.append(Hairpin(kind, chords[0], chords[-1])))

    def request_text(self):
        chords = self.selected_chords(include_rests=True)
        texts = [s.chord for s in self.selection if s.kind == "text"]
        target = (texts or chords or [None])[0]
        if target is None:
            self.message.emit("텍스트를 붙일 음표를 먼저 선택하세요.")
            return
        self.text_edit_requested.emit(target)

    def set_text(self, chord: Chord, text: str):
        text = text.strip() or None
        if text == chord.text:
            return

        def run():
            chord.text = text
        self._edit(run)

    def delete_selection(self):
        if not self.selection:
            return
        items = list(self.selection)

        def run():
            for s in items:
                if s.kind == "note":
                    self.editor.delete(s.chord, s.note)
                elif s.kind == "hairpin":
                    if s.hairpin in self.score.hairpins:
                        self.score.hairpins.remove(s.hairpin)
                elif s.kind == "text":
                    s.chord.text = None
        self._edit(run)

    def add_measure(self):
        self._edit(lambda: self.score.measures.append(Measure()))

    def set_time_signature(self, numerator: int, denominator: int) -> bool:
        if (numerator, denominator) == (self.score.numerator, self.score.denominator):
            return True

        def run():
            self.editor.set_time_signature(numerator, denominator, self.confirm_overflow)
        ok = self._edit(run)
        if ok:
            self.cursor = (0, F(0))
            self.selection = []
            self.changed.emit()
        return ok

    def undo(self):
        if self._undo:
            self._redo.append(self._snapshot())
            self._restore(self._undo.pop())
            self.changed.emit()
            self.state_changed.emit()

    def redo(self):
        if self._redo:
            self._undo.append(self._snapshot())
            self._restore(self._redo.pop())
            self.changed.emit()
            self.state_changed.emit()

    def escape(self):
        self.clear_selection()
