from fractions import Fraction

from .model import (Chord, Hairpin, INSTRUMENTS, Measure, Note, Score, TupletGroup)


def frac_str(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else \
        f"{value.numerator}/{value.denominator}"


def _note_to_json(n: Note):
    if not n.rimshot and not n.grace:
        return n.instrument
    d = {"instrument": n.instrument}
    if n.rimshot:
        d["rimshot"] = True
    if n.grace:
        d["grace"] = n.grace
    return d


def _chord_to_json(c: Chord) -> dict:
    d = {"duration": frac_str(c.base)}
    if c.dots:
        d["dots"] = c.dots
    if c.is_rest:
        d["rest"] = True
    else:
        d["notes"] = [_note_to_json(n) for n in c.notes]
    if c.articulations:
        d["articulations"] = sorted(c.articulations)
    if c.tremolo:
        d["tremolo"] = c.tremolo
    if c.stem_flipped:
        d["stem_flipped"] = True
    if c.tie_forward:
        d["tie"] = True
    if c.text:
        d["text"] = c.text
    if c.beam:
        d["beam"] = c.beam
    return d


def score_to_json(score: Score) -> dict:
    paths = {} 
    measures = []
    for mi, m in enumerate(score.measures):
        voices = []
        for v, events in enumerate(m.voices):
            out = []
            for i, item in enumerate(events):
                if isinstance(item, TupletGroup):
                    for j, c in enumerate(item.events):
                        paths[id(c)] = [mi, v, i, j]
                    out.append({"tuplet": f"{item.actual}:{item.normal}",
                                "unit": frac_str(item.unit),
                                "events": [_chord_to_json(c) for c in item.events]})
                else:
                    paths[id(item)] = [mi, v, i]
                    out.append(_chord_to_json(item))
            voices.append(out)
        measures.append({"voices": voices})
    hairpins = [{"kind": h.kind, "start": paths[id(h.start)], "end": paths[id(h.end)]}
                for h in score.hairpins if id(h.start) in paths and id(h.end) in paths]
    return {"measures": measures, "hairpins": hairpins}


def _note_from_json(d) -> Note:
    if isinstance(d, str):
        d = {"instrument": d}
    if d["instrument"] not in INSTRUMENTS:
        raise ValueError(f"알 수 없는 악기: {d['instrument']}")
    return Note(d["instrument"], bool(d.get("rimshot")), d.get("grace"))


def _chord_from_json(d: dict) -> Chord:
    notes = [] if d.get("rest") else [_note_from_json(n) for n in d.get("notes", [])]
    return Chord(Fraction(d["duration"]), int(d.get("dots", 0)), notes,
                 set(d.get("articulations", [])), d.get("tremolo"),
                 bool(d.get("stem_flipped")), bool(d.get("tie")), d.get("text"),
                 d.get("beam"))


def score_from_json(data: dict, numerator: int, denominator: int) -> Score:
    score = Score(numerator, denominator, [])
    for m in data.get("measures", []):
        measure = Measure()
        for v, events in enumerate(m.get("voices", [])[:2]):
            items = []
            for e in events:
                if "tuplet" in e:
                    actual, normal = (int(x) for x in e["tuplet"].split(":"))
                    items.append(TupletGroup(actual, normal, Fraction(e["unit"]),
                                             [_chord_from_json(c) for c in e["events"]]))
                else:
                    items.append(_chord_from_json(e))
            measure.voices[v] = items
        score.measures.append(measure)
    if not score.measures:
        score.measures.append(Measure())

    def resolve(path):
        item = score.measures[path[0]].voices[path[1]][path[2]]
        return item.events[path[3]] if len(path) > 3 else item

    for h in data.get("hairpins", []):
        try:
            score.hairpins.append(Hairpin(h["kind"], resolve(h["start"]), resolve(h["end"])))
        except (IndexError, KeyError):
            continue
    return score
