import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .notation.model import Score
from .notation.serialize import score_from_json, score_to_json
from .storage import data_dir, ensure_data_dirs, preset_dir

FORMAT = "RandomDrumSheet.preset"
VERSION = 1
DEFAULT_DIFFICULTIES = [str(i) for i in range(1, 11)]
INVALID_NAME_CHARS = '\\/:*?"<>|'
RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                  *(f"LPT{i}" for i in range(1, 10))}
MAX_EMPTY_MEASURES = 8


@dataclass
class PresetMeta:
    name: str = ""
    difficulty: Optional[str] = None
    tags: list = field(default_factory=list)
    path: Optional[Path] = None


def name_error(name: str) -> Optional[str]:
    if not name:
        return "프리셋 이름을 입력하세요."
    if any(ch in INVALID_NAME_CHARS for ch in name):
        return '파일 이름에 쓸 수 없는 문자(\\ / : * ? " < > |)가 포함되어 있습니다'
    if name.upper() in RESERVED_NAMES or name.endswith("."):
        return "사용할 수 없는 이름입니다."
    return None


def _write_json(path: Path, data: dict):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def same_file(a: Optional[Path], b: Optional[Path]) -> bool:
    return a is not None and b is not None and \
        os.path.normcase(str(a.resolve())) == os.path.normcase(str(b.resolve()))


class PresetStore:
    def __init__(self, presets: Optional[Path] = None, data: Optional[Path] = None):
        if presets is None:
            ensure_data_dirs()
        self.preset_dir = presets or preset_dir()
        self.difficulty_file = (data or data_dir()) / "difficulties.json"
        self.preset_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, name: str) -> Path:
        return self.preset_dir / f"{name}.json"

    def presets(self) -> list:
        result = []
        for path in sorted(self.preset_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(data, dict) and data.get("format") == FORMAT:
                result.append((path, data))
        return result

    def load(self, path: Path) -> tuple:
        data = json.loads(path.read_text(encoding="utf-8"))
        score = score_from_json(data.get("score", {}), data["numerator"], data["denominator"])
        return data, score

    def save(self, meta: PresetMeta, score: Score) -> Path:
        path = self.path_for(meta.name)
        now = datetime.now().isoformat(timespec="seconds")
        created = now
        if path.exists():
            try:
                created = json.loads(path.read_text(encoding="utf-8")).get("created", now)
            except (OSError, ValueError):
                pass
        _write_json(path, {
            "format": FORMAT,
            "version": VERSION,
            "name": meta.name,
            "difficulty": meta.difficulty,
            "time_signature": f"{score.numerator}/{score.denominator}",
            "numerator": score.numerator,
            "denominator": score.denominator,
            "measures": len(score.measures),
            "empty": score.is_empty(),
            "tags": list(meta.tags),
            "created": created,
            "modified": now,
            "score": score_to_json(score),
        })
        return path

    def rename(self, path: Path, new_name: str) -> Path:
        target = self.path_for(new_name)
        if target.exists() and not same_file(target, path):
            raise FileExistsError(new_name)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["name"] = new_name
        _write_json(path, data)
        os.replace(path, target)
        return target

    def delete(self, path: Path):
        path.unlink()

    def all_tags(self) -> list:
        tags = {t for _, d in self.presets() for t in d.get("tags", []) if isinstance(t, str)}
        return sorted(tags)

    def empty_presets(self) -> dict:
        return {d.get("measures"): (p, d.get("name", p.stem))
                for p, d in self.presets() if d.get("empty")}

    def difficulties(self) -> list:
        try:
            data = json.loads(self.difficulty_file.read_text(encoding="utf-8"))
            items = data.get("difficulties")
            if isinstance(items, list):
                return [str(x) for x in items]
        except (OSError, ValueError):
            pass
        return list(DEFAULT_DIFFICULTIES)

    def _save_difficulties(self, items: list):
        self.difficulty_file.parent.mkdir(parents=True, exist_ok=True)
        _write_json(self.difficulty_file, {"difficulties": items})

    def add_difficulty(self, name: str):
        items = self.difficulties()
        items.append(name)
        self._save_difficulties(items)

    def difficulty_users(self, name: str) -> list:
        return [p for p, d in self.presets() if d.get("difficulty") == name]

    def rename_difficulty(self, old: str, new: str):
        self._save_difficulties([new if x == old else x for x in self.difficulties()])
        self._set_difficulty_in_presets(old, new)

    def remove_difficulty(self, name: str):
        self._save_difficulties([x for x in self.difficulties() if x != name])
        self._set_difficulty_in_presets(name, None)

    def _set_difficulty_in_presets(self, old: str, new: Optional[str]):
        for path, data in self.presets():
            if data.get("difficulty") == old:
                data["difficulty"] = new
                _write_json(path, data)
