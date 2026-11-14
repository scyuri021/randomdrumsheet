from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QVBoxLayout)

from ..presets import MAX_EMPTY_MEASURES, PresetMeta, PresetStore, name_error, same_file
from . import style
from .dialogs import confirm, message
from .difficulty import DIALOG_FLAGS, DifficultyInput, DifficultyManager, _button, \
    ask_new_difficulty
from .score_preview import preview_area
from .tag_editor import TagEditor

FONT = QFont(style.BUTTON_FONT_FAMILY, 10)
BOLD = QFont(style.BUTTON_FONT_FAMILY, 10, QFont.Bold)

TOP_DIALOG_FLAGS = DIALOG_FLAGS | Qt.WindowStaysOnTopHint


def _label(text: str, bold=False) -> QLabel:
    label = QLabel(text)
    label.setFont(BOLD if bold else FONT)
    return label


class DuplicateDialog(QDialog):

    def __init__(self, parent, name: str, existing_score):
        super().__init__(parent, TOP_DIALOG_FLAGS)
        self.setWindowTitle("중복된 이름")
        self.setWindowModality(Qt.ApplicationModal)
        title = _label("중복된 이름의 프리셋이 존재합니다", bold=True)
        sub = _label(f"기존 프리셋: {name}")
        ask = _label("덮어씌우겠습니까?")
        overwrite = _button("덮어쓰기")
        cancel = _button("취소")
        overwrite.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addWidget(ask)
        buttons.addStretch(1)
        buttons.addWidget(overwrite)
        buttons.addWidget(cancel)
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(sub)
        layout.addWidget(preview_area(existing_score, 9.0), 1)
        layout.addLayout(buttons)
        self.resize(900, 420)


class SavePresetDialog(QDialog):

    def __init__(self, parent, store: PresetStore, score, meta: PresetMeta,
                 lock_name: bool = False):
        super().__init__(parent, TOP_DIALOG_FLAGS)
        self.setWindowTitle("프리셋 저장")
        self.setWindowModality(Qt.ApplicationModal)
        self.store = store
        self.score = score
        self.own_path = meta.path
        self.saved_meta = None

        time_sig = QLineEdit(f"{score.numerator}/{score.denominator}")
        time_sig.setReadOnly(True)
        time_sig.setFont(BOLD)
        time_sig.setFixedWidth(70)
        time_sig.setAlignment(Qt.AlignCenter)
        time_sig.setFocusPolicy(Qt.NoFocus)
        self.difficulty = DifficultyInput(store.difficulties(), meta.difficulty)
        add = _button("난이도 추가")
        add.clicked.connect(self._add_difficulty)
        manage = _button("난이도 관리")
        manage.clicked.connect(self._manage_difficulties)
        top = QHBoxLayout()
        top.addWidget(_label("박자", bold=True))
        top.addWidget(time_sig)
        top.addSpacing(24)
        top.addWidget(_label("난이도", bold=True))
        top.addWidget(self.difficulty)
        top.addWidget(add)
        top.addWidget(manage)
        top.addStretch(1)
        top.addWidget(_label(f"{len(score.measures)}마디"))

        self.name = QLineEdit(meta.name)
        self.name.setFont(FONT)
        self.name.setPlaceholderText("프리셋 이름 (필수)")
        if lock_name:
            self.name.setReadOnly(True)
            self.name.setFocusPolicy(Qt.NoFocus)
            self.name.setStyleSheet("QLineEdit { background: #ececee; color: #555; }")
            self.name.setToolTip("이름을 바꾸려면 '다른 이름으로 저장'을 쓰거나,\n"
                                 "불러오기 창에서 우클릭 -> 이름 바꾸기를 써 주세요.")
        self.tags = TagEditor(store.all_tags(), meta.tags)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignTop)
        form.addRow(_label("프리셋 이름", bold=True), self.name)
        form.addRow(_label("태그", bold=True), self.tags)
        save = _button("저장")
        save.setFont(BOLD)
        save.setMinimumWidth(110)
        save.clicked.connect(self._save)
        bottom = QHBoxLayout()
        bottom.addLayout(form, 1)
        bottom.addSpacing(16)
        bottom.addWidget(save, 0, Qt.AlignBottom)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addLayout(top)
        layout.addWidget(preview_area(score, 9.0), 1)
        layout.addLayout(bottom)
        self.resize(1100, 640)
        self.name.setFocus()

    def _add_difficulty(self):
        name = ask_new_difficulty(self, self.store)
        if name:
            self.difficulty.set_items(self.store.difficulties())
            self.difficulty.set_value(name)

    def _manage_difficulties(self):
        manager = DifficultyManager(self, self.store)
        manager.renamed.connect(lambda old, new: self.difficulty.value() == old
                                and self.difficulty.set_value(new))
        manager.removed.connect(lambda name: self.difficulty.value() == name
                                and self.difficulty.set_value(None))
        manager.exec()
        self.difficulty.set_items(self.store.difficulties())

    def _save(self):
        name = self.name.text().strip()
        error = name_error(name)
        if error:
            message(self, error)
            self.name.setFocus()
            return
        if not self.difficulty.validate():
            return
        target = self.store.path_for(name)
        if self.score.is_empty() and not self._confirm_empty(target):
            return
        if target.exists() and not same_file(target, self.own_path):
            try:
                _, existing = self.store.load(target)
            except (OSError, ValueError, KeyError):
                existing = None
            if existing is not None:
                if DuplicateDialog(self, name, existing).exec() != QDialog.Accepted:
                    return
            elif not confirm(self, "중복된 이름의 프리셋이 존재합니다\n덮어씌우겠습니까?",
                             "덮어쓰기", "취소"):
                return
        meta = PresetMeta(name, self.difficulty.value(), self.tags.tags())
        try:
            meta.path = self.store.save(meta, self.score)
        except OSError as e:
            message(self, f"저장하지 못했습니다.\n{e}")
            return
        self.saved_meta = meta
        self.accept()

    def _confirm_empty(self, target) -> bool:
        measures = len(self.score.measures)
        if measures > MAX_EMPTY_MEASURES:
            message(self, f"내용 없는 프리셋은 {MAX_EMPTY_MEASURES}마디까지만 저장할 수 있습니다.")
            return False
        existing = self.store.empty_presets().get(measures)
        if existing is not None and not same_file(existing[0], target) \
                and not same_file(existing[0], self.own_path):
            message(self, f"내용 없는 프리셋이 이미 존재합니다. 저장할 수 없습니다. ({existing[1]})")
            return False
        return confirm(self, "내용이 없습니다. 저장하시겠습니까?")
