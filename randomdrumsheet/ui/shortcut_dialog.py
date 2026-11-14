from PySide6.QtGui import QFont, QKeySequence
from PySide6.QtWidgets import (QDialog, QFrame, QGridLayout, QHBoxLayout, QKeySequenceEdit, QLabel,
                               QLineEdit, QPushButton, QVBoxLayout)

from . import style
from .dialogs import confirm, message
from .difficulty import DIALOG_FLAGS
from .shortcuts import ACTIONS, DEFAULTS, FIXED_KEYS, LABELS, ShortcutSettings, normalize

FONT = QFont(style.BUTTON_FONT_FAMILY, 10)
BOLD = QFont(style.BUTTON_FONT_FAMILY, 11, QFont.Bold)
SECTIONS = [
    ("악기 입력", "drum."),
    ("편집", "edit."),
    ("모드, 표기", ("mode.", "art.")),
]


def _button(text: str) -> QPushButton:
    b = QPushButton(text)
    b.setFont(FONT)
    b.setAutoDefault(False)
    b.setMinimumWidth(70)
    return b


class ShortcutDialog(QDialog):
    def __init__(self, parent, shortcut_settings: ShortcutSettings):
        super().__init__(parent, DIALOG_FLAGS)
        self.setWindowTitle("단축키 설정")
        self.settings = shortcut_settings
        self.values = dict(shortcut_settings.values)
        self.edits = {}
        self._updating = False

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        hint = QLabel("칸을 누른 뒤 설정할 키를 누르세요.")
        hint.setFont(FONT)
        layout.addWidget(hint)

        for title, prefix in SECTIONS:
            heading = QLabel(title)
            heading.setFont(BOLD)
            layout.addWidget(heading)
            grid = QGridLayout()
            grid.setHorizontalSpacing(12)
            grid.setVerticalSpacing(6)
            row = 0
            for action_id, label, _ in ACTIONS:
                if not action_id.startswith(prefix):
                    continue
                name = QLabel(label)
                name.setFont(FONT)
                name.setMinimumWidth(150)
                edit = QKeySequenceEdit(QKeySequence(self.values[action_id]))
                edit.setFont(FONT)
                edit.setMaximumSequenceLength(1)
                edit.setMinimumWidth(200)
                inner = edit.findChild(QLineEdit)
                if inner is not None:
                    inner.setPlaceholderText("비어 있음")
                edit.editingFinished.connect(lambda a=action_id: self._edited(a))
                edit.keySequenceChanged.connect(lambda _seq, a=action_id: self._maybe_cleared(a))
                clear = _button("지우기")
                clear.clicked.connect(lambda _=False, a=action_id: self._clear(a))
                grid.addWidget(name, row, 0)
                grid.addWidget(edit, row, 1)
                grid.addWidget(clear, row, 2)
                self.edits[action_id] = edit
                row += 1
            layout.addLayout(grid)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #b8b8bb;")
        layout.addWidget(line)
        fixed = QLabel("고정 단축키 (변경불가): 1~7 음표 길이, 점, 쉼표, Esc 선택 해제"
                       "Backspace 삭제Ctrl+Y / Ctrl+Shift+Z 다시 하기 Ctrl+S 저장")
        fixed.setFont(FONT)
        fixed.setWordWrap(True)
        fixed.setStyleSheet("QLabel { color: #555; }")
        layout.addWidget(fixed)

        reset = _button("기본값으로")
        reset.clicked.connect(self._reset)
        cancel = _button("취소")
        cancel.clicked.connect(self.reject)
        save = _button("저장")
        save.setFont(BOLD)
        save.clicked.connect(self._save)
        buttons = QHBoxLayout()
        buttons.addWidget(reset)
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    def _set_edit(self, action_id: str, key: str):
        self._updating = True
        self.edits[action_id].setKeySequence(QKeySequence(key))
        self._updating = False

    def _maybe_cleared(self, action_id: str):
        if not self._updating and self.edits[action_id].keySequence().isEmpty():
            self.values[action_id] = ""

    def _edited(self, action_id: str):
        if self._updating:
            return
        key = normalize(self.edits[action_id].keySequence().toString(QKeySequence.PortableText))
        if key == self.values[action_id]:
            return
        if not key:
            self.values[action_id] = ""
            return
        if key in FIXED_KEYS:
            message(self, f"'{key}'는 '{FIXED_KEYS[key]}'에 고정된 단축키이므로 쓸 수 없습니다.")
            self._set_edit(action_id, self.values[action_id])
            return
        owner = next((a for a, v in self.values.items() if a != action_id and v == key), None)
        if owner is not None:
            if not confirm(self, f"'{key}'는 이미 '{LABELS[owner]}'에 쓰이고 있습니다.\n"
                                 f"'{LABELS[action_id]}'(으)로 옮기시겠습니까?", "옮기기", "취소"):
                self._set_edit(action_id, self.values[action_id])
                return
            self.values[owner] = ""
            self._set_edit(owner, "")
        self.values[action_id] = key

    def _clear(self, action_id: str):
        self.values[action_id] = ""
        self._set_edit(action_id, "")

    def _reset(self):
        self.values = dict(DEFAULTS)
        for action_id, key in self.values.items():
            self._set_edit(action_id, key)

    def _save(self):
        for action_id in self.edits:
            self._edited(action_id)
        self.settings.save(self.values)
        self.accept()
