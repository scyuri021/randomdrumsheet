import json
import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QKeySequence

from ..storage import data_dir

ACTIONS = [
    ("drum.snare", "스네어", ""),
    ("drum.hihat", "하이햇", ""),
    ("drum.open_hihat", "오픈하이햇", ""),
    ("drum.bass", "베이스", ""),
    ("drum.mid_tom", "미들탐", ""),
    ("drum.small_tom", "스몰탐", ""),
    ("drum.floor_tom", "플로어탐", ""),
    ("drum.ride", "라이드", ""),
    ("drum.bell", "벨", ""),
    ("drum.crash", "크래시", ""),
    ("edit.undo", "뒤로가기", "Ctrl+Z"),
    ("edit.copy", "복사", "Ctrl+C"),
    ("edit.paste", "붙여넣기", "Ctrl+V"),
    ("edit.delete", "삭제", "Delete"),
    ("mode.select", "선택/입력모드 전환", ""),
    ("art.hihat_open", "하이햇 열기", ""),
    ("art.hihat_closed", "하이햇 닫기", ""),
    ("mode.rimshot", "림샷 모드 전환", ""),
]
DEFAULTS = {action_id: key for action_id, _, key in ACTIONS}
LABELS = {action_id: label for action_id, label, _ in ACTIONS}

FIXED = {"preset.save": "Ctrl+S"}
FIXED_KEYS = {
    **{str(i): "음표 길이" for i in range(1, 8)},
    ".": "점",
    "0": "쉼표",
    "Backspace": "삭제",
    "Esc": "선택 해제",
    "Ctrl+Y": "다시 하기",
    "Ctrl+Shift+Z": "다시 하기",
    "Ctrl+S": "저장",
}


def normalize(text: str) -> str:
    return QKeySequence(text).toString(QKeySequence.PortableText) if text else ""


class ShortcutSettings(QObject):
    changed = Signal()

    def __init__(self, path: Optional[Path] = None):
        super().__init__()
        self.path = path or data_dir() / "shortcuts.json"
        self.values = dict(DEFAULTS)
        self.load()

    def load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8")).get("shortcuts", {})
        except (OSError, ValueError, AttributeError):
            return
        for action_id in DEFAULTS:
            if isinstance(data.get(action_id), str):
                self.values[action_id] = normalize(data[action_id])

    def save(self, values: dict):
        self.values = {action_id: normalize(values.get(action_id, "")) for action_id in DEFAULTS}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps({"shortcuts": self.values}, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        os.replace(tmp, self.path)
        self.changed.emit()

    def key(self, action_id: str) -> QKeySequence:
        return QKeySequence(self.values.get(action_id, ""))


_settings: Optional[ShortcutSettings] = None


def settings() -> ShortcutSettings:
    global _settings
    if _settings is None:
        _settings = ShortcutSettings()
    return _settings


def shortcut(action_id: str) -> QKeySequence:
    if action_id in FIXED:
        return QKeySequence(FIXED[action_id])
    return settings().key(action_id)
