import copy
from dataclasses import dataclass, field
from fractions import Fraction
from math import ceil
from typing import Callable, Optional

F = Fraction
BASE_DURATIONS = [F(1, 2 ** i) for i in range(7)]
VALID_DENOMINATORS = (1, 2, 4, 8, 16, 32, 64)


def notated_length(base: Fraction, dots: int) -> Fraction:
    return base * (2 - F(1, 2 ** dots))


@dataclass(frozen=True)
class Instrument:
    key: str
    name: str
    line: int
    head: str
    voice: int
    articulation: Optional[str] = None


INSTRUMENTS = {i.key: i for i in [
    Instrument("bass", "베이스", 7, "normal", 1),
    Instrument("snare", "스네어", 3, "normal", 0),
    Instrument("crash", "크래시", -3, "circle_x", 0),
    Instrument("ride", "라이드", 0, "x", 0),
    Instrument("bell", "벨", 0, "diamond", 0),
    Instrument("hihat", "하이햇", -1, "x", 0),
    Instrument("open_hihat", "오픈하이햇", -1, "x", 0, articulation="hihat_open"),
    Instrument("small_tom", "스몰탐", 1, "normal", 0),
    Instrument("mid_tom", "미들탐", 2, "normal", 0),
    Instrument("floor_tom", "플로어탐", 5, "normal", 0),
]}
INSTRUMENT_BY_NAME = {i.name: i for i in INSTRUMENTS.values()}
EXCLUSIVE_ARTICULATIONS = [{"hihat_open", "hihat_closed"}]

TREMOLO_STROKES = {"tremolo8": 1, "tremolo16": 2, "tremolo32": 3, "tremolo64": 4, "buzz": 0}
TUPLET_KINDS = {"triplet": (3, 2), "sextuplet": (6, 4)}


@dataclass(eq=False)
class Note:
    instrument: str
    rimshot: bool = False
    grace: Optional[str] = None

    @property
    def info(self) -> Instrument:
        return INSTRUMENTS[self.instrument]

    @property
    def head(self) -> str:
        return "x" if self.rimshot else self.info.head

    def copy(self, keep_grace=True) -> "Note":
        return Note(self.instrument, self.rimshot, self.grace if keep_grace else None)


@dataclass(eq=False)
class Chord:
    base: Fraction
    dots: int = 0
    notes: list = field(default_factory=list)
    articulations: set = field(default_factory=set)
    tremolo: Optional[str] = None
    stem_flipped: bool = False
    tie_forward: bool = False
    text: Optional[str] = None
    beam: Optional[str] = None

    @property
    def is_rest(self) -> bool:
        return not self.notes

    @property
    def length(self) -> Fraction:
        return notated_length(self.base, self.dots)

    def make_rest(self):
        self.notes.clear()
        self.articulations.clear()
        self.tremolo = None
        self.stem_flipped = False
        self.tie_forward = False
        self.beam = None

    def continuation(self, base, dots) -> "Chord":
        if self.is_rest:
            return Chord(base, dots)
        return Chord(base, dots, [n.copy(keep_grace=False) for n in self.notes],
                     stem_flipped=self.stem_flipped)


@dataclass(eq=False)
class TupletGroup:
    actual: int
    normal: int
    unit: Fraction
    events: list = field(default_factory=list)

    @property
    def length(self) -> Fraction:
        return self.unit * self.normal

    @property
    def inner_capacity(self) -> Fraction:
        return self.unit * self.actual

    @property
    def ratio(self) -> Fraction:
        return F(self.normal, self.actual)


@dataclass(eq=False)
class Hairpin:
    kind: str
    start: Chord
    end: Chord


@dataclass
class Measure:
    voices: list = field(default_factory=lambda: [[], []])
    time_sig: Optional[tuple] = None
    repeat_start: bool = False
    repeat_end: bool = False
    ending: Optional[int] = None


@dataclass
class Score:
    numerator: int = 4
    denominator: int = 4
    measures: list = field(default_factory=lambda: [Measure()])
    hairpins: list = field(default_factory=list)

    @property
    def capacity(self) -> Fraction:
        return F(self.numerator, self.denominator)

    def time_sig_of(self, measure: int) -> tuple:
        return self.measures[measure].time_sig or (self.numerator, self.denominator)

    def capacity_of(self, measure: int) -> Fraction:
        return F(*self.time_sig_of(measure))

    def is_empty(self) -> bool:
        return all(c.is_rest for _, _, _, c, _ in self.chords())

    def chords(self):
        for mi, m in enumerate(self.measures):
            for v, events in enumerate(m.voices):
                for s, item in onsets(events):
                    if isinstance(item, TupletGroup):
                        for ls, c in onsets(item.events):
                            yield mi, v, item, c, s + ls * item.ratio
                    else:
                        yield mi, v, None, item, s

def _aligned(pos: Fraction, base: Fraction) -> bool:
    return (pos / base).denominator == 1

def rest_pieces(start: Fraction, end: Fraction) -> Optional[list]:
    pieces, pos = [], start
    while pos < end:
        for base in BASE_DURATIONS:
            if base <= end - pos and _aligned(pos, base):
                pieces.append((base, 0))
                pos += base
                break
        else:
            return None
    return pieces


_NOTE_CANDIDATES = sorted(((notated_length(b, d), b, d) for b in BASE_DURATIONS for d in (0, 1)),
                          reverse=True)


def note_pieces(length: Fraction) -> Optional[list]:
    pieces, rest = [], length
    while rest > 0:
        for total, b, d in _NOTE_CANDIDATES:
            if total <= rest:
                pieces.append((b, d))
                rest -= total
                break
        else:
            return None
    return pieces


def onsets(events) -> list:
    result, pos = [], F(0)
    for item in events:
        result.append((pos, item))
        pos += item.length
    return result


def assemble(timeline: list, capacity: Fraction) -> Optional[list]:
    result, pos = [], F(0)
    for s, item in sorted(timeline, key=lambda t: t[0]) + [(capacity, None)]:
        if s > pos:
            gap = rest_pieces(pos, s)
            if gap is None:
                return None
            result.extend(Chord(b, d) for b, d in gap)
        if item is not None:
            result.append(item)
            pos = s + item.length
    return result


def place(events: list, capacity: Fraction, start: Fraction, items: list) -> Optional[list]:

    end = start + sum((i.length for i in items), F(0))
    placed, pos = [], start
    for item in items:
        placed.append((pos, item))
        pos += item.length
    return overwrite(events, capacity, start, end, placed)


def overwrite(events: list, capacity: Fraction, start: Fraction, end: Fraction,
              placed: list) -> Optional[list]:
    timeline = []
    for s, item in onsets(events):
        if s + item.length <= start or s >= end:
            timeline.append((s, item))
        elif isinstance(item, Chord) and not item.is_rest and s < start:
            pieces = note_pieces(start - s)
            if pieces is None:
                return None
            chain = [item] + [item.continuation(b, d) for b, d in pieces[1:]]
            item.base, item.dots = pieces[0]
            pos = s
            for i, c in enumerate(chain):
                c.tie_forward = i < len(chain) - 1
                timeline.append((pos, c))
                pos += c.length
    return assemble(timeline + list(placed), capacity)


def normalize(events: list) -> list:
    if all(isinstance(i, Chord) and i.is_rest and not i.text for i in events):
        return []
    return events



class EditError(Exception):

    def __init__(self, message: Optional[str]):
        super().__init__(message)
        self.message = message


@dataclass
class Location:
    measure: int
    voice: int
    group: Optional[TupletGroup]
    onset: Fraction


ConfirmFn = Callable[[], bool]


@dataclass
class Clip:
    length: Fraction
    voices: dict


class ScoreEditor:

    def __init__(self, score: Score):
        self.score = score

    def locate(self, chord: Chord) -> Location:
        for mi, v, group, c, t in self.score.chords():
            if c is chord:
                return Location(mi, v, group, t)
        raise KeyError("chord not in score")

    def tuplet_at(self, measure: int, voice: int, tick: Fraction):
        for s, item in onsets(self.score.measures[measure].voices[voice]):
            if isinstance(item, TupletGroup) and s <= tick < s + item.length:
                return s, item
        return None

    def event_at(self, measure: int, voice: int, tick: Fraction) -> Optional[Chord]:
        for mi, v, _, c, t in self.score.chords():
            if mi == measure and v == voice and t == tick:
                return c
        return None

    def voice_chords(self, voice: int) -> list:
        return [c for _, v, _, c, _ in self.score.chords() if v == voice]

    def insert(self, measure: int, tick: Fraction, chord: Chord, voice: int,
               confirm_new_measures: ConfirmFn) -> tuple:
        cap = self.score.capacity
        found = self.tuplet_at(measure, voice, tick) or self._matching_tuplet(measure, voice, tick)
        if found is not None:
            g_start, group = found
            local = (tick - g_start) / group.ratio
            if local + chord.length > group.inner_capacity:
                raise EditError("잇단음표 묶음을 넘는 길이는 넣을 수 없습니다.")
            new = place(group.events, group.inner_capacity, local, [chord])
            if new is None:
                raise EditError("이 위치에는 입력할 수 없습니다.")
            group.events[:] = new
            return self._advance(measure, tick + chord.length * group.ratio)

        total = chord.length
        if tick + total <= cap:
            self._place_measure(measure, voice, tick, [chord])
            return self._advance(measure, tick + total)

        remaining = total - (cap - tick)
        need = ceil(remaining / cap)
        missing = measure + need - (len(self.score.measures) - 1)
        if missing > 0:
            if not confirm_new_measures():
                raise EditError(None)
            self.score.measures.extend(Measure() for _ in range(missing))

        segments = [cap - tick] + [min(cap, remaining - i * cap) for i in range(need)]
        chain = []
        for i, seg in enumerate(segments):
            pieces = rest_pieces(F(0), seg) if chord.is_rest else note_pieces(seg)
            if pieces is None:
                raise EditError("이 길이는 마디에 나누어 넣을 수 없습니다.")
            items = []
            for b, d in pieces:
                if not chain:
                    chord.base, chord.dots = b, d
                    item = chord
                else:
                    item = chord.continuation(b, d)
                items.append(item)
                chain.append(item)
            self._place_measure(measure + i, voice, tick if i == 0 else F(0), items)
        if not chord.is_rest:
            for i, c in enumerate(chain):
                c.tie_forward = i < len(chain) - 1
        return self._advance(measure + need, segments[-1])

    def _place_measure(self, measure: int, voice: int, tick: Fraction, items: list):
        events = self.score.measures[measure].voices[voice]
        new = place(events, self.score.capacity, tick, items)
        if new is None:
            raise EditError("이 위치에는 입력할 수 없습니다.")
        events[:] = new

    def _matching_tuplet(self, measure: int, voice: int, tick: Fraction):
        other = self.tuplet_at(measure, 1 - voice, tick)
        if other is None:
            return None
        g_start, src = other
        for s, item in onsets(self.score.measures[measure].voices[voice]):
            if s < g_start + src.length and s + item.length > g_start:
                if not (isinstance(item, Chord) and item.is_rest):
                    raise EditError("다른 부분의 잇단음표와 겹쳐서 입력할 수 없습니다.")
        group = TupletGroup(src.actual, src.normal, src.unit,
                            [Chord(src.unit) for _ in range(src.actual)])
        self._place_measure(measure, voice, g_start, [group])
        return g_start, group

    def cursor_after(self, chord: Chord) -> tuple:
        loc = self.locate(chord)
        ratio = loc.group.ratio if loc.group else 1
        return self._advance(loc.measure, loc.onset + chord.length * ratio)

    def _advance(self, measure: int, tick: Fraction) -> tuple:
        if tick >= self.score.capacity and measure + 1 < len(self.score.measures):
            return measure + 1, F(0)
        return measure, tick

    def add_note(self, chord: Chord, note: Note) -> Note:
        for n in chord.notes:
            if n.instrument == note.instrument:
                return n
        chord.notes.append(note)
        return note

    def change_duration(self, chord: Chord, base: Fraction, dots: int,
                        confirm_new_measures: ConfirmFn):
        loc = self.locate(chord)
        container = loc.group.events if loc.group else \
            self.score.measures[loc.measure].voices[loc.voice]
        container[container.index(chord)] = Chord(chord.base, chord.dots)
        chord.base, chord.dots, chord.tie_forward = base, dots, False
        self.insert(loc.measure, loc.onset, chord, loc.voice, confirm_new_measures)

    def make_tuplet(self, measure: int, voice: int, tick: Fraction, span: Fraction,
                    kind: str, first: Optional[Chord] = None) -> TupletGroup:
        actual, normal = TUPLET_KINDS[kind]
        unit = span / normal
        if unit not in BASE_DURATIONS:
            raise EditError("이 음표 길이로는 잇단음표를 만들 수 없습니다.")
        if self.tuplet_at(measure, voice, tick) is not None:
            raise EditError("잇단음표 안에는 잇단음표를 만들 수 없습니다.")
        if tick + span > self.score.capacity:
            raise EditError("잇단음표가 마디를 넘습니다.")
        events = [Chord(unit) for _ in range(actual)]
        if first is not None:
            first.base, first.dots, first.tie_forward = unit, 0, False
            events[0] = first
        group = TupletGroup(actual, normal, unit, events)
        self._place_measure(measure, voice, tick, [group])
        return group

    def delete(self, chord: Chord, note: Optional[Note]):
        if chord.is_rest:
            return
        if note is not None and len(chord.notes) > 1:
            chord.notes.remove(note)
        else:
            chord.make_rest()

    def span_start(self, chord: Chord) -> Fraction:
        loc = self.locate(chord)
        onset = self._group_onset(loc) if loc.group else loc.onset
        return loc.measure * self.score.capacity + onset

    def _group_onset(self, loc: Location) -> Fraction:
        for s, item in onsets(self.score.measures[loc.measure].voices[loc.voice]):
            if item is loc.group:
                return s
        raise KeyError("tuplet not found")

    def copy_range(self, chords: list) -> Clip:
        cap = self.score.capacity
        start, end, voices = None, None, set()
        for c in chords:
            loc = self.locate(c)
            voices.add(loc.voice)
            a = self.span_start(c)
            b = a + (loc.group.length if loc.group else c.length)
            start = a if start is None else min(start, a)
            end = b if end is None else max(end, b)
        clip = Clip(end - start, {})
        for v in sorted(voices):
            items = []
            for mi, m in enumerate(self.score.measures):
                base = mi * cap
                if base >= end or base + cap <= start:
                    continue
                for s, item in onsets(m.voices[v]):
                    a, b = base + s, base + s + item.length
                    if b <= start or a >= end or a < start:
                        continue
                    if isinstance(item, Chord) and item.is_rest and not item.text:
                        continue
                    if b <= end:
                        items.append((a - start, copy.deepcopy(item)))
                    elif isinstance(item, Chord):
                        cut = copy.deepcopy(item)
                        cut.base, cut.dots = note_pieces(end - a)[0]
                        cut.tie_forward = False
                        items.append((a - start, cut))
            clip.voices[v] = items
        return clip

    def paste(self, clip: Clip, start: Fraction, choose_overflow: Callable[[], str]) -> list:
        cap = self.score.capacity
        limit = start + clip.length
        total = len(self.score.measures) * cap
        if limit > total:
            choice = choose_overflow()
            if choice == "extend":
                self.score.measures.extend(Measure() for _ in range(ceil((limit - total) / cap)))
            elif choice == "truncate":
                limit = total
            else:
                raise EditError(None)

        pasted = []
        for v, items in clip.voices.items():
            per_measure = {}
            for off, original in items:
                item = copy.deepcopy(original)
                a = start + off
                if a >= limit:
                    continue
                if isinstance(item, TupletGroup):
                    mi, local = int(a // cap), a % cap
                    if a + item.length > limit:
                        continue
                    if local + item.length > cap:
                        raise EditError("잇단음표가 마디선에 걸려 붙여넣을 수 없습니다.")
                    per_measure.setdefault(mi, []).append((local, item))
                    pasted.extend(c for c in item.events if not c.is_rest)
                    continue
                tie_after = item.tie_forward
                pos, remaining, chain = a, min(item.length, limit - a), []
                while remaining > 0:
                    mi, local = int(pos // cap), pos % cap
                    seg = min(remaining, cap - local)
                    pieces = rest_pieces(local, local + seg) if item.is_rest else note_pieces(seg)
                    if pieces is None:
                        raise EditError("이 위치에는 붙여넣을 수 없습니다.")
                    for b, d in pieces:
                        if not chain:
                            item.base, item.dots = b, d
                            piece = item
                        else:
                            piece = item.continuation(b, d)
                        per_measure.setdefault(mi, []).append((local, piece))
                        chain.append(piece)
                        local += piece.length
                    pos += seg
                    remaining -= seg
                if not item.is_rest:
                    for i, c in enumerate(chain):
                        c.tie_forward = tie_after if i == len(chain) - 1 else True
                    pasted.append(item)

            for mi in range(int(start // cap), ceil(limit / cap)):
                base = mi * cap
                rs, re = max(start, base) - base, min(limit, base + cap) - base
                events = self.score.measures[mi].voices[v]
                new = overwrite(events, cap, rs, re, per_measure.get(mi, []))
                if new is None:
                    raise EditError("이 위치에는 붙여넣을 수 없습니다.")
                events[:] = new
        return pasted

    def set_time_signature(self, numerator: int, denominator: int,
                           confirm_new_measures: ConfirmFn):
        if denominator not in VALID_DENOMINATORS:
            raise EditError("분모는 1, 2, 4, 8, 16, 32, 64 중 하나여야 합니다.")
        if numerator < 1:
            raise EditError("분자는 1 이상이어야 합니다.")
        cap = F(numerator, denominator)
        if any(self._content_end(m) > cap for m in self.score.measures) \
                and not confirm_new_measures():
            raise EditError(None)

        new_measures = []
        for m in self.score.measures:
            per_voice = [self._pour(events, cap) for events in m.voices]
            count = max(1, *(len(p) for p in per_voice))
            for i in range(count):
                new_measures.append(Measure([p[i] if i < len(p) else [] for p in per_voice]))
        self.score.numerator, self.score.denominator = numerator, denominator
        self.score.measures = new_measures

    @staticmethod
    def _content_end(measure: Measure) -> Fraction:
        end = F(0)
        for events in measure.voices:
            for s, item in onsets(events):
                if not (isinstance(item, Chord) and item.is_rest and not item.text):
                    end = max(end, s + item.length)
        return end

    @staticmethod
    def _pour(events: list, cap: Fraction) -> list:
        slots = {}
        for s, item in onsets(events):
            idx, local = int(s // cap), s % cap
            if isinstance(item, Chord) and item.is_rest:
                if item.text and local + item.length <= cap:
                    slots.setdefault(idx, []).append((local, item))
                continue
            if isinstance(item, TupletGroup):
                if local + item.length > cap:
                    idx, local = idx + 1, F(0)
                slots.setdefault(idx, []).append((local, item))
                continue
            if local + item.length <= cap:
                slots.setdefault(idx, []).append((local, item))
                continue
            chain, remaining, first = [], item.length, True
            while remaining > 0:
                seg = min(cap - local, remaining)
                pos = local
                for b, d in note_pieces(seg):
                    if first:
                        item.base, item.dots = b, d
                        c, first = item, False
                    else:
                        c = item.continuation(b, d)
                    slots.setdefault(idx, []).append((pos, c))
                    chain.append(c)
                    pos += c.length
                remaining -= seg
                idx, local = idx + 1, F(0)
            for i, c in enumerate(chain):
                c.tie_forward = i < len(chain) - 1
        if not slots:
            return []
        result = []
        for i in range(max(slots) + 1):
            assembled = assemble(slots.get(i, []), cap) if i in slots else []
            result.append(normalize(assembled or []))
        return result

    def cleanup(self):
        for m in self.score.measures:
            for v in range(2):
                m.voices[v][:] = normalize(m.voices[v])
        for voice in (0, 1):
            chords = self.voice_chords(voice)
            for c, nxt in zip(chords, chords[1:] + [None]):
                if c.tie_forward and (nxt is None or not {n.instrument for n in c.notes}
                                      & {n.instrument for n in nxt.notes}):
                    c.tie_forward = False
        alive = {c for _, _, _, c, _ in self.score.chords()}
        self.score.hairpins = [h for h in self.score.hairpins
                               if h.start in alive and h.end in alive
                               and not h.start.is_rest]
