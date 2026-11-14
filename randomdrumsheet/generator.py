import copy
import random
from dataclasses import dataclass, field

from .notation.model import Score, ScoreEditor

IMPOSSIBLE_EACH_ONCE = "조건 실현 불가능: 무조건 한 개씩 포함 옵션을 해제하거나 마디수를 조정해 주세요."
IMPOSSIBLE_FILL = "조건 실현 불가능: 선택한 프리셋으로 총 마디수를 정확히 채울 수 없습니다."


class GenerationError(Exception):
    pass


@dataclass
class SheetOptions:
    title: str = ""
    total_measures: int = 32
    per_line: int = 4
    each_once: bool = True
    repeats: bool = False
    max_repeats: int = 1


@dataclass
class GeneratedSheet:
    score: Score
    options: SheetOptions
    order: list = field(default_factory=list)
    repeats: list = field(default_factory=list)
    voltas: list = field(default_factory=list)


VOLTA_CHANCE = 0.5


@dataclass
class RepeatSection:
    start: int
    end: int
    second_ending: bool = False

    @property
    def span(self) -> int:
        return self.end - self.start + 1 + (1 if self.second_ending else 0)



def _fill(candidates: list, lengths: list, remaining: int, rng) -> list:
    if remaining == 0:
        return []
    lens = {lengths[i] for i in candidates}
    reach = [True] + [False] * remaining
    for s in range(1, remaining + 1):
        reach[s] = any(L <= s and reach[s - L] for L in lens)
    if not reach[remaining]:
        raise GenerationError(IMPOSSIBLE_FILL)
    picked, r = [], remaining
    while r > 0:
        options = [i for i in candidates if lengths[i] <= r and reach[r - lengths[i]]]
        choice = rng.choice(options)
        picked.append(choice)
        r -= lengths[choice]
    return picked


def _subset(candidates: list, lengths: list, total: int, rng) -> list:
    order = list(candidates)
    rng.shuffle(order)
    mask = (1 << (total + 1)) - 1
    can = [0] * (len(order) + 1)
    can[-1] = 1
    for i in range(len(order) - 1, -1, -1):
        can[i] = (can[i + 1] | (can[i + 1] << lengths[order[i]])) & mask
    if not (can[0] >> total) & 1:
        raise GenerationError(IMPOSSIBLE_FILL)
    picked, r = [], total
    for i, idx in enumerate(order):
        L = lengths[idx]
        take = r >= L and (can[i + 1] >> (r - L)) & 1
        skip = (can[i + 1] >> r) & 1
        if take and (not skip or rng.random() < 0.5):
            picked.append(idx)
            r -= L
    return picked


def choose_presets(lengths: list, total: int, each_once: bool, rng=None) -> list:
    rng = rng or random.Random()
    n = len(lengths)
    if n == 0:
        raise GenerationError("선택된 프리셋이 없습니다")
    if each_once:
        if sum(lengths) > total:
            raise GenerationError(IMPOSSIBLE_EACH_ONCE)
        sequence = list(range(n)) + _fill(list(range(n)), lengths, total - sum(lengths), rng)
    else:
        usable = [i for i, L in enumerate(lengths) if L <= total]
        if not usable:
            raise GenerationError(IMPOSSIBLE_FILL)
        if n > total:
            sequence = _subset(usable, lengths, total, rng)
        else:
            sequence = _fill(usable, lengths, total, rng)
    rng.shuffle(sequence)
    return sequence


def max_repeat_sections(item_count: int) -> int:
    return (item_count + 1) // 2


def place_repeats(item_count: int, max_count: int, rng=None) -> list:
    rng = rng or random.Random()
    limit = min(max_count, max_repeat_sections(item_count))
    if limit < 1:
        return []
    k = rng.randint(1, limit)
    sizes = [3 if rng.random() < VOLTA_CHANCE else rng.choice((1, 2)) for _ in range(k)]
    while sum(sizes) + (k - 1) > item_count:
        j = rng.choice([j for j, s in enumerate(sizes) if s > 1])
        sizes[j] -= 1
    free = item_count - sum(sizes) - (k - 1)
    slots = [0] * (k + 1)
    for _ in range(free):
        slots[rng.randrange(k + 1)] += 1
    sections, pos = [], slots[0]
    for j, size in enumerate(sizes):
        if size == 3:
            sections.append(RepeatSection(pos, pos + 1, second_ending=True))
        else:
            sections.append(RepeatSection(pos, pos + size - 1))
        pos += size
        if j < k - 1:
            pos += 1 + slots[j + 1]
    return sections


def generate(presets: list, options: SheetOptions, rng=None) -> GeneratedSheet:
    rng = rng or random.Random()
    lengths = [len(score.measures) for _, score in presets]
    sequence = choose_presets(lengths, options.total_measures, options.each_once, rng)

    sheet = Score(4, 4, [])
    result = GeneratedSheet(sheet, options)
    starts = []
    for idx in sequence:
        name, source = presets[idx]
        part = copy.deepcopy(source)
        for voice in range(2):
            chords = [c for _, v, _, c, _ in part.chords() if v == voice]
            if chords:
                chords[-1].tie_forward = False
        for m in part.measures:
            m.time_sig = (part.numerator, part.denominator)
            m.repeat_start = m.repeat_end = False
            m.ending = None
        starts.append(len(sheet.measures))
        sheet.measures.extend(part.measures)
        sheet.hairpins.extend(part.hairpins)
        result.order.append(name)
    sheet.numerator, sheet.denominator = sheet.measures[0].time_sig

    def item_measures(item: int) -> range:
        return range(starts[item], starts[item] + lengths[sequence[item]])

    if options.repeats:
        for section in place_repeats(len(sequence), options.max_repeats, rng):
            a = starts[section.start]
            b = item_measures(section.end)[-1]
            sheet.measures[a].repeat_start = True
            sheet.measures[b].repeat_end = True
            result.repeats.append((a, b))
            if section.second_ending:
                first = item_measures(section.end)
                second = item_measures(section.end + 1)
                for m in first:
                    sheet.measures[m].ending = 1
                for m in second:
                    sheet.measures[m].ending = 2
                result.voltas.append(((first[0], first[-1]), (second[0], second[-1])))
    ScoreEditor(sheet).cleanup()
    return result
